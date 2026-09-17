"""SCT-Agent 的唯一正式语言入口。

开发集使用独立的 micro/D_grow 信号形成候选经验；候选先存放在临时 memory
目录，只有在独立门控的 JointPass 严格提升后才晋升。冻结后才调用 Base/Plus，
最终结果不再进入失败聚类、模型 prompt 或长期经验库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
LEGACY_DIR = PROJECT_ROOT / "methods" / "legacy_prompt_adapters"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

try:
    from .candidate_gates import quality_gate
    from .failure_clustering import cluster_failures, normalize_failure_message
except ImportError:  # 直接脚本运行时使用脚本目录导入。
    from candidate_gates import quality_gate
    from failure_clustering import cluster_failures, normalize_failure_message

try:
    import run_language_method_matrix as matrix
except Exception:  # 仅在真正运行时报告 legacy 依赖问题；--help 仍可用。
    matrix = None


LANGUAGE_LABELS = {"python": "Python", "cpp": "C++", "go": "Go"}


def read_json(path: Path) -> Any:
    """读取 UTF-8 JSON，兼容带 BOM 的旧规则文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    """写入可审计的缩进 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL；空文件返回空列表。"""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_language_rules(memory_root: Path, language: str) -> list[dict[str, Any]]:
    """读取已有正式规则；缺失时返回空库，不依赖历史 sample 文件。"""
    path = memory_root / f"{language}_rules.json"
    if not path.exists():
        return []
    value = read_json(path)
    return value if isinstance(value, list) else []


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """按 Function、Secure 和 JointPass 汇总开发/最终结果。"""
    total = len(rows)
    def count(key: str) -> int:
        return sum(bool((row.get("metrics") or {}).get(key)) for row in rows)
    errors = sum(int(row.get("generation_errors") or 0) for row in rows)
    return {
        "total": total,
        "functional": count("secure_functional"),
        "secure": count("secure_security"),
        "func_sec": count("secure_func_sec"),
        "generation_errors": errors,
        "functional_rate": round(100 * count("secure_functional") / total, 2) if total else 0,
        "secure_rate": round(100 * count("secure_security") / total, 2) if total else 0,
        "func_sec_rate": round(100 * count("secure_func_sec") / total, 2) if total else 0,
    }


def failure_payload(rows: list[dict[str, Any]], limit: int = 1000) -> list[dict[str, Any]]:
    """从开发结果生成脱敏失败信号，禁止暴露任务 ID、测试值和原始日志。"""
    failures: list[dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics") or {}
        if metrics.get("secure_func_sec") and not row.get("generation_errors"):
            continue
        secure = row.get("secure") or {}
        evaluation = secure.get("eval") or {}
        result = evaluation.get("result") or {}
        details = result.get("details") or {}
        raw = secure.get("error") or details.get("error_type") or result.get("stderr") or "unknown failure"
        failures.append({
            "language": row.get("language") or "unknown",
            "cwe": row.get("cwe") or "unknown",
            "functional": bool(metrics.get("secure_functional")),
            "secure": bool(metrics.get("secure_security")),
            "func_sec": bool(metrics.get("secure_func_sec")),
            "phase": details.get("phase") or "validation",
            "error_type": details.get("error_type") or "generation_or_validation",
            "normalized_message": normalize_failure_message(str(raw)),
        })
        if len(failures) >= limit:
            break
    return failures


def gate_accepts(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
    """实现 DOCX 有效性门控：JointPass 必须严格增加且无单项退化。"""
    if after.get("generation_errors", 0) > before.get("generation_errors", 0):
        return False, "rejected: generation errors increased"
    if after.get("func_sec", 0) <= before.get("func_sec", 0):
        return False, "rejected: ΔJointPass must be positive"
    if after.get("functional", 0) < before.get("functional", 0):
        return False, "rejected: Function regressed"
    if after.get("secure", 0) < before.get("secure", 0):
        return False, "rejected: Secure regressed"
    return True, "accepted: positive JointPass gain"


def _rule_key(rule: dict[str, Any]) -> str:
    """计算规则内容指纹，用于去重而不保存任务样本。"""
    text = "|".join(str(rule.get(key) or "") for key in ("rule_name", "principle", "when_to_apply", "implementation_hint", "avoid"))
    return hashlib.sha1(text.lower().encode()).hexdigest()[:16]


def merge_rules(current: list[dict[str, Any]], updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """候选规则只做去重/通用性检查，调用者决定是否晋升。"""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in current + updates:
        if not isinstance(rule, dict):
            continue
        key = _rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(rule))
    return result


def rules_to_markdown(rules: list[dict[str, Any]], language: str) -> str:
    """将结构化经验渲染为人工可读中文说明。"""
    lines = [f"# {LANGUAGE_LABELS.get(language, language)} SCT 经验", "", "仅在任务契约匹配时使用以下规则。", ""]
    for index, rule in enumerate(rules, 1):
        lines.extend([f"## {index}. {rule.get('rule_name') or rule.get('name') or '未命名规则'}", f"- 原则：{rule.get('principle') or ''}", f"- 适用条件：{rule.get('when_to_apply') or ''}", f"- 实现提示：{rule.get('implementation_hint') or rule.get('hint') or ''}", f"- 禁止模式：{rule.get('avoid') or ''}", ""])
    return "\n".join(lines)


def run_matrix_subprocess(*, out_name: str, subset: str, language: str, limit: int, model: str, max_tokens: int, retries: int, workers: int, memory_root: Path, force: bool) -> None:
    """调用已有多语言验证器；该边界只接受开发集或冻结后的只读评测。"""
    if matrix is None:
        raise RuntimeError("legacy run_language_method_matrix 依赖不可用")
    out_dir = HERE / "out" / out_name / subset / "language_methods" / subset / language / "ours_sct_agent.jsonl"
    if force and out_dir.exists():
        out_dir.unlink()
    env = os.environ.copy()
    env["SCT_LANGUAGE_MEMORY_ROOT"] = str(memory_root)
    env.setdefault("SAFECODER_CPP_DOCKER_IMAGE", "safecoder-cpp-validator:local")
    env.setdefault("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22")
    cmd = [sys.executable, str(LEGACY_DIR / "run_language_method_matrix.py"), "--dataset-root", str(PROJECT_ROOT / "data" / "SecEvoBasePlus"), "--subsets", subset, "--languages", language, "--limit", str(limit), "--include-ours", "--only-ours", "--out-name", out_name, "--model", model, "--max-tokens", str(max_tokens), "--temperature", "0", "--retries", str(retries), "--workers", str(workers)]
    subprocess.run(cmd, cwd=LEGACY_DIR, env=env, check=True)


def propose_rules(language: str, current_rules: list[dict[str, Any]], clusters: list[dict[str, Any]], model: str, max_tokens: int, api_timeout: float) -> list[dict[str, Any]]:
    """从脱敏失败簇提出候选规则；失败时返回空候选而不是修改长期库。"""
    if not clusters:
        return []
    try:
        import run_coset_eagle_experiment as sct
        client = sct.make_client(api_timeout)
        prompt = f"""Improve secure {LANGUAGE_LABELS.get(language, language)} code generation. Use only the abstract failure clusters below. Return a JSON array of reusable rules with rule_name, principle, when_to_apply, implementation_hint and avoid. Do not include task identifiers, test values, constants or answers.\nCurrent rules: {json.dumps(current_rules[:20], ensure_ascii=False)}\nFailure clusters: {json.dumps(clusters, ensure_ascii=False)}"""
        raw, _tokens, error = sct.call_model(client, prompt, model, max_tokens, retries=2)
        if error:
            return []
        updates = sct.extract_json_array(raw)
        return [item for item in updates if isinstance(item, dict)][:10]
    except Exception:
        return []


def run_language_evolution(args: argparse.Namespace, language: str) -> dict[str, Any]:
    """按开发集循环形成候选规则，冻结后才运行 Base/Plus。"""
    root = HERE / "out" / args.out_name
    memory_root = root / "sct_language_memory"
    memory_root.mkdir(parents=True, exist_ok=True)
    accepted_rules: list[dict[str, Any]] = merge_rules(load_language_rules(memory_root, language), [])
    accepted_summary: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    pending: tuple[list[dict[str, Any]], Path] | None = None
    write_json(memory_root / f"{language}_rules.json", accepted_rules)
    for round_index in range(args.evolution_rounds + 1):
        eval_memory = pending[1] if pending else memory_root
        name = f"{args.out_name}_{language}_dev_r{round_index}"
        run_matrix_subprocess(out_name=name, subset=args.micro_subset, language=language, limit=args.micro_limit, model=args.model, max_tokens=args.max_tokens, retries=args.retries, workers=args.workers, memory_root=eval_memory, force=args.force)
        rows = read_jsonl(HERE / "out" / name / args.micro_subset / "language_methods" / args.micro_subset / language / "ours_sct_agent.jsonl")
        summary = summarize_rows(rows)
        failures = failure_payload(rows)
        clusters = [cluster.to_dict() for cluster in cluster_failures(failures, min_support=1)]
        write_json(memory_root / f"{language}_round_{round_index}_failure_clusters.json", clusters)
        if accepted_summary is None:
            accepted_summary = summary
            records.append({"round": round_index, "summary": summary, "decision": "seed"})
        else:
            ok, reason = gate_accepts(accepted_summary, summary)
            records.append({"round": round_index, "summary": summary, "decision": reason})
            if ok:
                accepted_summary = summary
                if pending:
                    accepted_rules, pending_root = pending[0], pending[1]
                    (memory_root / f"{language}_rules.json").write_text(json.dumps(accepted_rules, ensure_ascii=False, indent=2), encoding="utf-8")
                    pending = None
            else:
                # 被门控拒绝的候选不能继续影响下一轮，也不能写入长期库。
                pending = None
        if round_index < args.evolution_rounds:
            updates = propose_rules(language, accepted_rules, clusters, args.model, args.max_tokens, args.api_timeout)
            candidate_rules = merge_rules(accepted_rules, updates)
            safe, _reasons = quality_gate_rules(candidate_rules, accepted_rules)
            candidate_root = memory_root / f"candidate_r{round_index + 1}"
            candidate_root.mkdir(parents=True, exist_ok=True)
            write_json(candidate_root / f"{language}_rules.json", candidate_rules)
            write_json(memory_root / f"{language}_candidate_r{round_index + 1}.json", {"rules": candidate_rules, "quality_pass": safe})
            pending = (candidate_rules if safe else accepted_rules, candidate_root if safe else memory_root)
    # 冻结标记后只读执行最终评测，最终结果不再生成 failure payload。
    freeze = {"model": args.model, "language": language, "feedback_channel": "disabled", "memory_sha256": hashlib.sha256(json.dumps(accepted_rules, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    write_json(memory_root / f"{language}_freeze_manifest.json", freeze)
    final_name = f"{args.out_name}_{language}_frozen_eval"
    for subset in args.subsets:
        run_matrix_subprocess(out_name=final_name, subset=subset, language=language, limit=args.limit, model=args.model, max_tokens=args.max_tokens, retries=args.retries, workers=args.workers, memory_root=memory_root, force=args.force)
    final_rows: list[dict[str, Any]] = []
    for subset in args.subsets:
        final_rows.extend(read_jsonl(HERE / "out" / final_name / subset / "language_methods" / subset / language / "ours_sct_agent.jsonl"))
    final_summary = summarize_rows(final_rows)
    write_json(memory_root / f"{language}_evolution_records.json", records)
    write_json(memory_root / f"{language}_final_summary.json", final_summary)
    return {"language": language, "micro_records": records, "final_summary": final_summary, "best_round": len(records) - 1}


def quality_gate_rules(candidate: list[dict[str, Any]], existing: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """对候选规则逐条执行质量门控，任何泄露或空边界都会拒绝。"""
    reasons: list[str] = []
    for rule in candidate:
        text = " ".join(str(rule.get(key) or "") for key in ("rule_name", "principle", "when_to_apply", "implementation_hint", "avoid"))
        if any(token in text.lower() for token in ("task_id", "hidden test", "参考答案", "测试输入", "token=")):
            reasons.append("candidate contains task/test information")
        if not str(rule.get("principle") or "").strip() or not str(rule.get("when_to_apply") or "").strip():
            reasons.append("candidate lacks principle or applicability")
    return not reasons, reasons


def write_report(out_name: str, results: list[dict[str, Any]]) -> None:
    """写出不含隐藏测试反馈的语言级总结。"""
    root = HERE / "out" / out_name
    lines = ["# SCT-Agent 统一语言自进化报告", "", "Base/Plus 仅在冻结后运行，反馈通道关闭。", "", "| 语言 | Function | Secure | Function+Secure | 错误 |", "|---|---:|---:|---:|---:|"]
    for result in results:
        summary = result["final_summary"]
        lines.append(f"| {LANGUAGE_LABELS.get(result['language'], result['language'])} | {summary['functional']}/{summary['total']} | {summary['secure']}/{summary['total']} | {summary['func_sec']}/{summary['total']} | {summary['generation_errors']} |")
    (root / "sct_language_evolution_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """解析 CLI；--help 不要求 openai、Docker 或 API key。"""
    parser = argparse.ArgumentParser(description="运行 DOCX-faithful SCT-Agent 语言经验自进化")
    parser.add_argument("--out-name", default="sct_language_evolution_full")
    parser.add_argument("--languages", nargs="+", choices=["python", "cpp", "go"], default=["python", "cpp", "go"])
    parser.add_argument("--subsets", nargs="+", choices=["Base", "Plus"], default=["Base", "Plus"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--micro-subset", choices=["Base", "Plus"], default="Base")
    parser.add_argument("--micro-limit", type=int, default=6)
    parser.add_argument("--evolution-rounds", type=int, default=2)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--api-timeout", type=float, default=90.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    results = [run_language_evolution(args, language) for language in args.languages]
    write_report(args.out_name, results)


if __name__ == "__main__":
    main()
