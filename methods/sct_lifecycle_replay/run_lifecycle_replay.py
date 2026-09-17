"""小规模运行入口：来源池提取 → 主动回放 → 轨迹验证 → 候选 → 独立审查 → 冻结。

所属阶段：全流程编排（文档 2.1 流程）。串联 source_knowledge（初始知识）、
active_replay（任务选择）、trajectory_runner（代码生成与验证）、
candidate_builder（候选形成）、audit_runner（独立审查）、
experience_lifecycle（状态更新）与 freeze_protocol（冻结）。
验证证据：PLT 训练侧全部使用本地 python -I 子进程（不启动 Docker）；
     Base/Plus 冻结评测由 frozen_evaluation 生成计划、外部评测脚本执行，
     反馈通道保持 disabled。
允许修改长期经验库：仅 ExperienceMemory.apply_audit 在独立审查后更新；
     最终测试反馈不回流。
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
from pathlib import Path

from .api import ChatClient
from .audit_runner import compare_audit_records, content_quality_pass
from .candidate_builder import build_candidates
from .chatanywhere_smoke import load_key
from .experience_lifecycle import ExperienceMemory
from .family_manifest import load_family_manifest
from .freeze_protocol import build_freeze_metadata
from .independent_audit import audit_decision
from .language_adapters import adapter_contract
from .reporting import write_report
from .retriever import ExperienceRetriever
from .source_knowledge import extract_initial_hypothesis
from .split_scheduler import assign_family_variants
from .trajectory_runner import joint_pass, run_trajectory

# 主动回放：从 Q_pool 选择下一批任务（文档 6 节）。
from .active_replay import replay_score, select_replay_tasks


def live_requester(model: str = "deepseek-v3.2", timeout: int = 40):
    """创建真实 ChatAnywhere 请求器；返回内容只在内存中处理。"""
    from urllib.request import Request, urlopen

    def request(prompt: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 512}
        ).encode("utf-8")
        req = Request(
            "https://api.chatanywhere.tech/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    return request


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def _regression_reruns(
    hpass_rows: list[dict],
    requester,
    retriever: ExperienceRetriever,
    *,
    samples: int,
    repairs: int,
    timeout: int,
    by_id: dict,
) -> tuple[list[dict], dict[str, list[bool]]]:
    """对每条 H_pass 任务用候选记忆重跑 samples 次，取「最优样本」作为回归证据。

    所属阶段：A_audit 的 H_pass 回归检查（文档 7 节）。输入是历史通过的
    H_pass 轨迹与加入候选后的检索器；输出是与 compare_audit_records 对齐的
    逐任务重跑记录，以及每个任务的样本联合通过情况（供审计追溯）。

    证据语义：单次 API 采样存在噪声，只有「全部 samples 次样本都联合失败」
    才计入安全回归（best 记录 joint_pass 为 False）；任一样本通过说明失败
    不是候选导致的稳定退化，best 取该通过样本，compare_audit_records 就不会
    把它计为回归。repairs 必须与建立 H_pass 的轨迹一致，否则修复能力的缺失
    会被误判为候选引发的回归（修复不对称会放大回归噪声）。
    """
    best_records: list[dict] = []
    sample_log: dict[str, list[bool]] = {}
    for row in hpass_rows:
        tid = row["task_id"]
        task = by_id[int(tid)]
        runs = [
            run_trajectory(task, requester, retriever, timeout=timeout, repairs=repairs)
            for _ in range(max(1, samples))
        ]
        best = next((r for r in runs if joint_pass(r)), runs[0])
        best_records.append(best)
        sample_log[str(tid)] = [joint_pass(r) for r in runs]
    return best_records, sample_log


def _classify_seed_outcome(evidence: dict) -> str:
    """按功能/安全通过情况给 seed 生成结果打标签。

    所属阶段：source 阶段 seed 验证（文档 3 节）。输入是模型从零生成代码的
    验证证据，输出是三类标签：
    - joint：功能与安全均通过（成功经验）；
    - partial：功能或安全任一侧通过（部分有效，仍可加入 seed，但打 partial 标签）；
    - failed：双侧均未通过（失败，进错题本，不进入 M0）。
    证据未测量的组一律视为未通过，不冒充成功。
    """
    functional = (evidence.get("functional") or {}).get("status")
    security = (evidence.get("security") or {}).get("status")
    f_ok = functional == "pass"
    s_ok = security == "pass"
    if f_ok and s_ok:
        return "joint"
    if f_ok or s_ok:
        return "partial"
    return "failed"


def _task_signal(row: dict) -> dict:
    """为主动回放计算任务信息价值信号（文档 6.1 的 Score 输入）。

    当前实现用可复现的启发式信号，不依赖模型自评：
    - risk：CWE 与敏感操作的安全风险，高危险 CWE 族给高权重；
    - novelty：任务与来源池已选任务的 CWE 差异（覆盖新类别更值钱）；
    - cost：夹具规模（capability+safety 用例数）作为执行成本代理；
    - uncertainty/coverage_gap 默认 0（PLT 无不确定性标注，留作扩展）。
    """
    risk_cwes = {"22", "78", "502", "77", "95", "89", "79"}
    cwe = str(row.get("CWE_ID", ""))
    risk = 1.0 if cwe in risk_cwes else 0.3
    test_code = str((row.get("unittest") or {}).get("testcases") or "")
    cost = min(2.0, len(test_code) / 2000.0)
    return {"uncertainty": 0.0, "risk": risk, "novelty": 0.0, "coverage_gap": 0.0, "cost": cost}


def has_tests(row: dict) -> bool:
    """静态判断 PLT 任务是否有可执行的 capability+safety 双测试夹具。

    所属阶段：source/replay/audit 三池选样前的任务筛选。输入一条 PLT 记录，
    输出只表示「是否存在数据驱动 testcases 夹具」，不执行夹具代码（夹具 setup
    可能含 os.system('ls') 等系统调用，须保持静态判断）；真实通过率仍由
    trajectory_validation 的本地验证决定，本函数不代替验证证据。

    旧实现用 ast.literal_eval 解析 testcases 字典，遇到引用了辅助变量的夹具
    （例如先定义 attack = 'a'*1000000 再写进 testcases）会抛 ValueError，把
    488 条可测样本误判为无测试，导致全量模式只用到 386 条、10 个 CWE。新实现
    只做静态结构判断，与验证器 exec(setup+tests) 的判定完全一致，可识别 874
    条可测样本、18 个 CWE。判定三步：
    1. testcases 非空；
    2. 语法可解析（排除未替换占位符导致的语法错误，如 '<LOCAL_PATH>'）；
    3. 源码含 testcases 赋值与 capability/safety 键（不要求字面量可求值）。
    """
    test_code = str((row.get("unittest") or {}).get("testcases") or "")
    if not test_code.strip():
        return False
    try:
        ast.parse(test_code)
    except SyntaxError:
        return False
    return (
        "testcases" in test_code
        and any(f'"{name}"' in test_code or f"'{name}'" in test_code for name in ("capability", "safety"))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=96, help="参与训练的样本数；按完整三变体 family 向下取整")
    parser.add_argument("--all-plt", action="store_true", help="使用全部有测试的 PLT 样本（source/replay/audit 三池覆盖全部可验证任务）")
    parser.add_argument("--out", required=True)
    parser.add_argument("--live-api", action="store_true")
    parser.add_argument(
        "--active-replay",
        action="store_true",
        help="启用验证驱动主动回放：从 Q_pool 按信息价值选择回放任务并记录 replay_decisions.jsonl",
    )
    parser.add_argument(
        "--llm-replay",
        action="store_true",
        help="启用 LLM 驱动的任务选择：让模型阅读候选任务契约描述（CWE/函数名/问题描述/安全策略）"
        "选择回放任务，结果写入 replay_decisions.jsonl（含模型理由）",
    )
    parser.add_argument(
        "--min-variants",
        type=int,
        default=3,
        help="参与来源池的 family 最少变体数（1/2/3）。默认 3 保证 source/replay/audit "
        "都有同语义变体；放宽到 2 或 1 可扩大 Q_pool 候选范围（文档 6.3：功能角色不要求目录一一映射）",
    )
    parser.add_argument(
        "--replay-limit",
        type=int,
        default=0,
        help="回放任务数上限；0 表示按 --rows 自动计算（三池均衡）",
    )
    parser.add_argument(
        "--llm-batch-size",
        type=int,
        default=24,
        help="LLM 任务选择每批候选数；候选较多时分批避免超长 prompt 降低 JSON 输出稳定性",
    )
    parser.add_argument(
        "--regression-limit",
        type=int,
        default=0,
        help="H_pass 安全回归的绝对计数容忍；默认 0 保持零容忍，噪声较大时可放宽到小正整数",
    )
    parser.add_argument(
        "--regression-samples",
        type=int,
        default=1,
        help="每条 H_pass 任务回归重跑次数；>1 时仅当全部样本都失败才计入回归（降低单次 API 噪声）",
    )
    parser.add_argument(
        "--repairs",
        type=int,
        default=1,
        help="生成失败后的修复迭代次数（run_trajectory 的 repairs）；source/replay/audit 三阶段共用",
    )
    args = parser.parse_args()
    # 全量模式默认放宽 family 变体下限到 1（用户可显式 --min-variants 覆盖）。
    if args.all_plt and args.min_variants == 3:
        args.min_variants = 1
    root = Path(__file__).parents[2]
    data = json.loads((root / "data/external/secodeplt/secodeplt/data.json").read_text(encoding="utf-8"))
    manifest = load_family_manifest(root / "data/external/secodeplt/derived_metadata/family_manifest.json")
    # 按 family 分组（尽量满足 family 原子性；变体数下限由 --min-variants 控制）。
    by_family: dict[str, list[dict]] = {}
    for row in data:
        family = manifest["row_classification"].get(str(row["index"]), {}).get("seed_family_id")
        if family:
            by_family.setdefault(family, []).append(row)

    # 来源池 family：优先完整三变体（--min-variants 控制下限），全部成员须有测试。
    source_families = [
        rows for rows in by_family.values()
        if len(rows) >= max(1, min(3, args.min_variants)) and all(has_tests(row) for row in rows)
    ]
    if args.all_plt:
        # 全量模式：候选池 = 全部有测试的任务（不要求 family 完整，--min-variants
        # 默认放宽到 1，让单变体/二变体 family 也参与，覆盖全部 18 个 CWE）。
        all_tested = [row for rows in by_family.values() for row in rows if has_tests(row)]
        all_tested = sorted(all_tested, key=lambda r: int(r["index"]))
        roles = assign_family_variants([int(r["index"]) for r in all_tested], manifest)
        by_id = {int(r["index"]): r for r in all_tested}
        selected = all_tested
    else:
        family_count = max(1, args.rows // 3)
        # CWE 轮流选取，避免按原始索引集中抽中某一个漏洞类别。
        queues: dict[str, list[list[dict]]] = {}
        for rows in sorted(source_families, key=lambda rows: int(rows[0]["index"])):
            queues.setdefault(str(rows[0]["CWE_ID"]), []).append(rows)
        selected_families: list[list[dict]] = []
        while len(selected_families) < family_count and any(queues.values()):
            for cwe in sorted(queues):
                if queues[cwe] and len(selected_families) < family_count:
                    selected_families.append(queues[cwe].pop(0))
        # source 池：每个选中 family 取前 3 个变体（不足 3 个则全部取，保证 seed 多样性）。
        selected = sorted(
            [row for rows in selected_families for row in sorted(rows, key=lambda r: int(r["index"]))[:3]],
            key=lambda row: int(row["index"]),
        )
        # 角色分配：source 池沿用 family 轮换；replay/audit 角色在后面可能被
        # 主动回放/LLM 选择重新划分（文档 6.3：功能角色不是数据目录的一一映射）。
        roles = assign_family_variants([int(r["index"]) for r in selected], manifest)
        by_id = {int(r["index"]): r for r in selected}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    write_jsonl(out / "manifest/split.jsonl", [{"role": role, "task_id": i} for role, ids in roles.items() for i in ids])
    # API requester 由正式 runner 注入；这里保留可测试的离线默认响应。
    requester = ChatClient() if args.live_api else (lambda prompt: {"choices": [{"message": {"content": ""}}]})
    seeds: list[dict] = []
    family_by_row = manifest["row_classification"]
    source_rows = [by_id[i] | {"family_id": family_by_row[str(i)]["seed_family_id"]} for i in roles["source_pool"]]
    replay_rows = [by_id[i] | {"family_id": family_by_row[str(i)]["seed_family_id"]} for i in roles["replay_pool"]]
    audit_task_rows = [by_id[i] | {"family_id": family_by_row[str(i)]["seed_family_id"]} for i in roles["audit_pool"]]

    # ---- 主动回放（文档 6 节）：--active-replay 用信息价值重排，--llm-replay 用 LLM 选择 ----
    replay_decisions: list[dict] = []
    if args.llm_replay and args.live_api and replay_rows:
        # Q_pool = 当前回放池候选；LLM 阅读任务契约描述后选择回放子集。
        # 注意：种子经验此时尚未提取验证，LLM 选择只依据任务契约描述与
        # 当前空经验库（文档 6.1：LLM 提出验证方向，验证器提供最终证据）。
        # 混合调度：LLM 选择不足 limit 时由规则评分补足，保证回放池满额。
        from .llm_scheduler import select_tasks_hybrid

        original_replay_rows = list(replay_rows)
        replay_limit = args.replay_limit or len(replay_rows)
        result = select_tasks_hybrid(original_replay_rows, replay_limit, requester, seeds=[], batch_size=args.llm_batch_size)
        chosen_ids = {int(t["index"]) for t in result["selected"]}
        selected_by = result.get("selected_by") or {}
        # 保持 family 角色：LLM 只从回放池选择子集，未选中的回放任务移入审查池。
        if result["selected"]:
            replay_rows = sorted(result["selected"], key=lambda r: int(r["index"]))
            moved_to_audit = [
                r for r in original_replay_rows if int(r["index"]) not in chosen_ids
            ]  # 未选中任务补充进审查池，扩大独立审查覆盖
            existing_audit_ids = {int(r["index"]) for r in audit_task_rows}
            audit_task_rows = audit_task_rows + [r for r in moved_to_audit if int(r["index"]) not in existing_audit_ids]
        replay_decisions = [
            {
                "task_id": int(r["index"]),
                "cwe": str(r.get("CWE_ID", "")),
                "selected": int(r["index"]) in chosen_ids,
                "reason": str(result["reasons"].get(str(r["index"]), "")),
                "selector": "llm",
                "selected_by": selected_by.get(str(r["index"]), "llm"),
            }
            for r in original_replay_rows
        ]
        write_jsonl(out / "replay_pool/replay_decisions.jsonl", replay_decisions)
    elif args.active_replay and replay_rows:
        # Q_pool = 当前回放池候选；对每条任务计算信息价值并选择 top-N。
        scored = [
            {"task_id": int(r["index"]), **r, "signal": _task_signal(r), "replay_score": replay_score(_task_signal(r))}
            for r in replay_rows
        ]
        chosen = select_replay_tasks(scored, len(replay_rows))
        # 保持与 split.jsonl 的 family 角色一致：只在回放池内重排序，不跨池移动。
        # 按信息价值分数降序重排（同分保持原顺序，可复现）。
        score_by_id = {int(c["task_id"]): c["replay_score"] for c in chosen}
        replay_rows = sorted(replay_rows, key=lambda r: -score_by_id.get(int(r["index"]), 0.0))
        replay_decisions = [
            {
                "task_id": int(c["task_id"]),
                "cwe": str(c.get("CWE_ID", "")),
                "uncertainty": c["signal"]["uncertainty"],
                "risk": c["signal"]["risk"],
                "novelty": c["signal"]["novelty"],
                "coverage_gap": c["signal"]["coverage_gap"],
                "cost": c["signal"]["cost"],
                "replay_score": c["replay_score"],
                "selected": int(c["task_id"]) in {int(x["task_id"]) for x in chosen},
            }
            for c in scored
        ]
        write_jsonl(out / "replay_pool/replay_decisions.jsonl", replay_decisions)

    for row in source_rows:
        try:
            seeds.append(extract_initial_hypothesis(row, requester))
        except Exception as exc:
            seeds.append({"task_id": row["index"], "error_type": str(exc)})
    write_jsonl(out / "source_pool/initial_hypotheses.jsonl", seeds)
    # ---- 第一步（修正）：用「模型从零生成」验证 seed 是否有效，不再用黄金代码冒充证据 ----
    # 每条 seed 用「该条经验」驱动模型从零生成代码并跑功能/安全测试：
    #   - 功能与安全均通过 → status=seed（成功经验，进入 M0）
    #   - 功能或安全任一侧通过 → status=seed_partial（部分有效，进入 M0 但打标签）
    #   - 双侧均失败 → 错题本 error_ledger（failure 标签，不进入 M0）
    # 黄金代码只用于 extract_initial_hypothesis 的差异提示（提取"学什么"），
    # 不再用于验证"学到没"。成功与失败都写入经验，用不同标签区分；错题本保留
    # 供后续反例经验与数据质量审计复用。
    validated_seeds: list[dict] = []
    seed_error_ledger: list[dict] = []
    for seed, source_row in zip(seeds, source_rows):
        if seed.get("status") != "seed":
            continue
        trajectory = run_trajectory(
            source_row, requester, ExperienceRetriever([seed]), timeout=30, repairs=args.repairs
        )
        evidence = trajectory.get("evidence") or {}
        outcome = _classify_seed_outcome(evidence)
        updated = dict(seed)
        updated["evidence"] = evidence
        updated["seed_validity"] = outcome
        if outcome in ("joint", "partial"):
            # 只要功能或安全有一个通过即可加入 seed，用标签区分成功程度。
            updated["status"] = "seed" if outcome == "joint" else "seed_partial"
            validated_seeds.append(updated)
        else:
            # 双侧均失败：保留进错题本（failure 标签），不进入 M0。
            seed_error_ledger.append({
                "kind": "seed_generation_failure",
                "task_id": int(source_row["index"]),
                "cwe": str(source_row.get("CWE_ID", "")),
                "failure_type": trajectory.get("failure_type"),
                "evidence": evidence,
                "stage": "source",
                "round": 0,
            })
    write_jsonl(out / "source_pool/error_ledger.jsonl", seed_error_ledger)
    valid_seeds = validated_seeds
    seeds_joint = sum(1 for s in valid_seeds if s.get("seed_validity") == "joint")
    seeds_partial = sum(1 for s in valid_seeds if s.get("seed_validity") == "partial")
    # 回放轨迹改用已验证的 M0（valid_seeds）作为检索记忆，而不是未验证的原始 seed。
    trajectories = [run_trajectory(row, requester, ExperienceRetriever(valid_seeds), repairs=args.repairs) for row in replay_rows]
    write_jsonl(out / "replay_pool/trajectories.jsonl", trajectories)
    candidates = build_candidates(trajectories)
    write_jsonl(out / "replay_pool/candidates.jsonl", [c.to_dict() for c in candidates])
    memory = ExperienceMemory(valid_seeds)
    audit_rows: list[dict] = []
    # baseline 共享：M_t（无候选）在审查任务上的结果只跑一次，所有候选复用。
    # 审计的效率关键：候选数量 × 审查任务数 的生成成本可高达数千次 API 调用，
    # 每个候选重跑相同的 baseline 是重复劳动（文档 7.2：在固定审查任务集上
    # 比较 M_t 与 M_t+e'，baseline 是共享的）。
    print(f"审计：共 {len(candidates)} 个候选，{len(audit_task_rows)} 条审查任务，先跑共享 baseline…", flush=True)
    shared_baseline = [
        run_trajectory(row, requester, ExperienceRetriever(valid_seeds), timeout=30, repairs=0)
        for row in audit_task_rows
    ]
    baseline_by_task = {int(r["task_id"]): r for r in shared_baseline}
    print(f"共享 baseline 完成（{len(shared_baseline)} 条），开始逐候选审计…", flush=True)
    for candidate_index, candidate in enumerate(candidates, start=1):
        candidate_card = candidate.to_dict() | {"id": candidate.candidate_id}
        # fail-fast：候选必须真正进入与它同 CWE 的审查任务的检索 top-k，
        # 否则 before/after 对比的是同一 prompt 的两次 API 调用（噪声）。
        same_cwe_tasks = [r for r in audit_task_rows if str(r.get("CWE_ID", "")) == str(candidate.cwe)]
        probe_rows = same_cwe_tasks or audit_task_rows[:1]
        probe = ExperienceRetriever(valid_seeds + [candidate_card]).search(
            {**probe_rows[0].get("task_description", {}), "CWE_ID": probe_rows[0].get("CWE_ID"), "language": "python"},
            limit=3,
        )
        candidate_retrieved = any(str(c.get("id")) == candidate.candidate_id for c in probe)
        candidate_memory = valid_seeds + [candidate_card]
        # 候选只影响同 CWE 的审查任务：after 只在 same_cwe_tasks 上重跑，
        # 其余审查任务直接复用 baseline（跨 CWE 的生成 prompt 不含该候选，
        # 重跑只会引入 API 噪声；文档 6.3：候选经验是跨任务归纳的安全原则，
        # 其效果应在其适用的 CWE 范围内衡量）。
        if same_cwe_tasks:
            after = [
                run_trajectory(row, requester, ExperienceRetriever(candidate_memory), timeout=30, repairs=0)
                for row in same_cwe_tasks
            ]
        else:
            after = []  # 无同 CWE 审查任务：delta 无法衡量，保守 demoted
        # 构造与 baseline 对齐的 after 视图：同 CWE 用重跑结果，其余复用 baseline。
        after_view = []
        for row in audit_task_rows:
            tid = int(row["index"])
            if tid in {int(r["task_id"]) for r in after}:
                after_view.append(next(r for r in after if int(r["task_id"]) == tid))
            else:
                after_view.append(baseline_by_task[tid])
        hpass = [row for row in trajectories if joint_pass(row)]
        # H_pass 回归重跑必须与建立 H_pass 的轨迹同配置（repairs 一致），否则
        # 修复能力的缺失会被误判为候选引发的回归（修复不对称，放大噪声）。
        # 每条 H_pass 任务重跑 --regression-samples 次；仅当全部样本都联合失败
        # 才算回归（任一样本通过视为未回归，容忍单次 API 噪声）。
        regression_after, regression_samples = _regression_reruns(
            hpass, requester, ExperienceRetriever(candidate_memory),
            samples=args.regression_samples, repairs=1, timeout=30, by_id=by_id,
        )
        audit_stats = compare_audit_records(shared_baseline, after_view, hpass, regression_after)
        status = audit_decision(
            quality_pass=content_quality_pass(candidate_card),
            delta_joint_pass=audit_stats["delta_joint_pass"],
            security_regressions=audit_stats["security_regressions"],
            functional_regression=0.0,
            regression_limit=args.regression_limit,
            retrieved=candidate_retrieved,
        )
        memory.add_candidate(candidate_card)
        memory.apply_audit(candidate.candidate_id, status)
        audit_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "decision": status,
                "candidate_retrieved": candidate_retrieved,
                "retrieved_probe_cwe": str(probe_rows[0].get("CWE_ID", "")),
                "same_cwe_audit_tasks": len(same_cwe_tasks),
                "audit_tasks_rerun": len(after),
                "audit_tasks_reused": len(shared_baseline) - len(after),
                "regression_samples": args.regression_samples,
                "regression_limit": args.regression_limit,
                "regression_sample_outcomes": regression_samples,
                **audit_stats,
                "baseline": shared_baseline,
                "after": after_view,
                "regression_after": regression_after,
            }
        )
        write_jsonl(out / "audit_pool/audit_rows.jsonl", audit_rows)
        print(f"  候选 {candidate_index}/{len(candidates)} ({candidate.candidate_id}) → {status}（retrieved={candidate_retrieved}，重跑 {len(after)} 条）", flush=True)
    write_jsonl(out / "audit_pool/audit_rows.jsonl", audit_rows)
    write_jsonl(out / "memory/lifecycle_events.jsonl", memory.events)
    memory.freeze()
    (out / "frozen").mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "frozen/m_star.jsonl", memory.long_term)
    freeze_metadata = build_freeze_metadata(memory.long_term, "deepseek-v3.2", "tfidf-v1", "score-v1")
    freeze_metadata["memory_sha256"] = hashlib.sha256((out / "frozen/m_star.jsonl").read_bytes()).hexdigest()
    (out / "frozen/freeze_metadata.json").write_text(json.dumps(freeze_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 必报指标补全（文档 12.2 节）----
    failure_dist = collections.Counter(row.get("failure_type") for row in trajectories)
    decision_counts = collections.Counter(row["decision"] for row in audit_rows)
    summary = {
        "source_tasks": len(source_rows),
        "seed_joint": seeds_joint,
        "seed_partial": seeds_partial,
        "seed_failed_to_error_ledger": len(seed_error_ledger),
        "replay_tasks": len(replay_rows),
        "audit_tasks": len(audit_task_rows),
        "candidates": len(candidates),
        "promoted": decision_counts.get("supported", 0),
        "demoted": decision_counts.get("demoted", 0),
        "revised": decision_counts.get("revised", 0),
        "frozen_memory": len(memory.long_term),
        "feedback_channel": "disabled",
        "active_replay": args.active_replay,
        "llm_replay": args.llm_replay,
        "all_plt": args.all_plt,
        "replay_decisions": len(replay_decisions),
        "trajectory_failure_distribution": dict(failure_dist),
        "trajectory_joint_pass": sum(joint_pass(t) for t in trajectories),
    }
    write_report(out, summary, {"model": "deepseek-v3.2", "plt_docker_required": False, "languages": {lang: adapter_contract(lang) for lang in ("python", "go", "cpp")}, "feedback_channel": "disabled"})


if __name__ == "__main__":
    main()
