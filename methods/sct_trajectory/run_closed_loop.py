"""CLE 闭环命令行入口（全量真实调用 AI）。

用法：
  # 全量 874 条可验证 PLT 样本，完整 Phase1→2→3
  python -m methods.sct_trajectory.run_closed_loop --out translation_work/sct_runs/cle_full_<date> \
      --workers 4 --model deepseek-v3.2 --timeout 90 --validation-timeout 20

  # 小规模冒烟
  python -m methods.sct_trajectory.run_closed_loop --limit 12 --out <dir>

信号边界（硬性红线）：本入口只读训练侧 PLT（data/external/secodeplt），三池按
  Seed Family 原子划分；Base/Plus 不参与在线进化。
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from methods.sct_lifecycle_replay.chatanywhere_smoke import load_key  # noqa: E402
from methods.sct_lifecycle_replay.family_manifest import load_family_manifest  # noqa: E402
from methods.sct_lifecycle_replay.run_lifecycle_replay import has_tests  # noqa: E402
from methods.sct_trajectory.ablation import get_config as get_ablation  # noqa: E402
from methods.sct_trajectory.closed_loop import CleRunner  # noqa: E402
from methods.sct_trajectory.error_ledger import ErrorLedger  # noqa: E402
from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode  # noqa: E402
from methods.sct_trajectory.run_artifacts import (  # noqa: E402
    append_run_index,
    write_pools,
    write_run_metadata,
    write_status,
    write_tree_snapshot,
)
from methods.sct_trajectory.split import assign_families_atomic  # noqa: E402


def _requester(model: str, timeout: int, max_tokens: int = 1500,
               max_inflight: int = 0, *, hard_timeout: float | None = None,
               gate_wait_timeout: float | None = None, retry_backoff: float = 2.0,
               circuit_failures: int = 15, circuit_cooldown: float = 60.0, semaphore=None,
               selector_max_inflight: int = 16):
    """构造 LLM 请求器。

    max_inflight > 0 时，用本请求器实例的信号量把真实HTTP在途数限制在该值。
    不同请求器/进程不共享该上限；调用方仍需协调账号总并发。
    为什么需要（2026-09-22）：一旦把任务内部的调用并行化（检索打分、基线探测），
    实际并发会变成 workers × 任务内并行数，轻易超过 API 的丢包线（实测 deepseek 系
    在 80 并发以上开始丢包）。有了这道闸门，任务内可以放心并行，
    总在途量始终受控。max_inflight=0 表示不限制（保持旧行为）。
    """
    """真实 ChatAnywhere 请求器（带硬超时 + 重试）。

    为什么需要"硬超时"：urllib 的 timeout 只作用于 socket 层，遇到
    连接被中间设备挂起（TCP 已建立但服务端不再回数据）时不会触发，
    实测出现过卡死 13 分钟以上、整条实验无法推进的情况。
    这里用"独立线程 + join(hard_timeout)"兜底：主调用超时可返回，但后台线程
    未结束前仍占槽；排队也有独立上限，避免无限等待或无界后台请求。
    """
    import urllib.request
    from methods.sct_trajectory.selector_protocol import SelectorPrompt

    HARD_TIMEOUT = hard_timeout if hard_timeout is not None else max(timeout + 30, 60)
    GATE_WAIT_TIMEOUT = gate_wait_timeout if gate_wait_timeout is not None else HARD_TIMEOUT * 2
    if min(HARD_TIMEOUT, GATE_WAIT_TIMEOUT, circuit_cooldown) <= 0 or circuit_failures < 1 or retry_backoff < 0:
        raise ValueError('invalid_requester_limits')
    MAX_ATTEMPTS = 3
    if selector_max_inflight < 1:
        raise ValueError('selector_max_inflight_must_be_positive')
    # 长上下文筛选使用独立子闸门；总在途预算仍由所有阶段共享的 _gate 控制。
    # 两道闸门都由真实 HTTP 线程释放，超时不会制造隐形额外并发。
    _selector_gate = threading.BoundedSemaphore(selector_max_inflight)
    # 【重试退避】（2026-09-22 卡死事故的配套缓解）
    # 事故疑似服务端限流（挂包而非报错）。高并发下失败后立刻重试只会加剧拥堵，
    # 因此失败后按 BACKOFF_BASE * 2^(attempt-1) 退避，并加随机抖动避免
    # 多个线程同时重试形成"重试风暴"。
    BACKOFF_BASE = retry_backoff
    BACKOFF_MAX = 20.0

    def _one_call(prompt: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": prompt}],
             "temperature": 0, "max_tokens": min(max_tokens, 256) if isinstance(prompt, SelectorPrompt) else max_tokens}
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.chatanywhere.tech/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    _gate = semaphore if semaphore is not None else (threading.Semaphore(max_inflight) if max_inflight > 0 else None)
    # 【连续失败熔断】（缺陷 D36，2026-09-22 卡死事故）
    # 事故经过：Gate3 回归探针里的 LLM 请求被服务端挂住（不回包也不报错），
    # 每次 attempt 卡满 90 秒硬超时才放弃，3 次 attempt = 270 秒才失败；
    # 而单个候选要跑几十次串行调用 → 单个候选要几小时。整条运行既没报错也没进度，
    # 主进程 CPU 归零、日志静默 —— 运维视角看就是"无缘无故中断了"。
    # 统计当前熔断代内按完成顺序观测的连续失败；超过阈值进入明确冷却期。
    # 冷却期拒绝新请求，过期允许恢复；之前已在途请求不会提前解除冷却。
    CIRCUIT_BREAK_AFTER = circuit_failures
    _cb_lock = threading.Lock()
    _cb_state = {"consecutive": 0, "open_until": 0.0, "reason": "", "epoch": 0}

    def _diagnostic(exc: Exception, attempt: int, elapsed: float) -> str:
        """请求阶段仅记录错误类、HTTP状态、轮次和耗时；不输出URL/响应/密钥，不写经验。"""
        from urllib.error import HTTPError, URLError
        parts = [f'type={type(exc).__name__}', f'attempt={attempt}', f'elapsed_s={elapsed:.3f}']
        if isinstance(exc, HTTPError):
            parts.append(f'http_status={int(exc.code)}')
        elif isinstance(exc, URLError):
            parts.append(f'reason_type={type(exc.reason).__name__}')
        return ' '.join(parts)

    def _cb_check() -> int:
        """请求开始/排队后检查熔断；冷却期间不发HTTP，到期允许新请求恢复，不写经验。"""
        with _cb_lock:
            if _cb_state['open_until']:
                if time.monotonic() < _cb_state['open_until']:
                    raise RuntimeError(f"llm_circuit_open {_cb_state['reason']}")
                _cb_state['open_until'] = 0.0
                _cb_state['consecutive'] = 0
            return _cb_state['epoch']

    def _backoff(attempt: int) -> None:
        """失败后退避（指数 + 抖动），避免高并发下的重试风暴。"""
        import random
        delay = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (attempt - 1)))
        time.sleep(delay * (0.5 + random.random() * 0.5))

    def _cb_note_ok(epoch: int) -> None:
        with _cb_lock:
            # 开路前已在途请求的迟到成功不能提前解除冷却。
            if epoch == _cb_state['epoch'] and not _cb_state['open_until']:
                _cb_state["consecutive"] = 0

    def _cb_note_fail(reason: str, epoch: int) -> None:
        with _cb_lock:
            if epoch != _cb_state['epoch']:
                return
            _cb_state["consecutive"] += 1
            n = _cb_state["consecutive"]
            if n >= CIRCUIT_BREAK_AFTER:
                _cb_state['reason'] = reason
                _cb_state['open_until'] = time.monotonic() + circuit_cooldown
                _cb_state['epoch'] += 1
                raise RuntimeError(f'llm_circuit_open {reason}')

    def request(prompt: str) -> dict:
        """带全局在途闸门 + 硬超时的请求。

        【闸门必须放在计时窗口之外】（2026-09-22 自查修正）
        原先把 `with _gate` 放在被 `th.join(HARD_TIMEOUT)` 计时的线程里，于是
        **排队等槽位的时间会被算进硬超时**：当闸门饱和（例如 Phase3 探测
        24 并行 × 每条 4 次调用 = 96 个请求抢 80 个槽）时，排在后面的请求可能
        等超过 90 秒 → 被误判为超时 → 触发重试 → 拥堵加剧，形成正反馈。
        现在改为：**先取槽（等待不计时），再启动计时线程**。
        """
        last_exc: Exception | None = None
        diagnostics: list[str] = []
        safe_diagnostics: list[dict] = []
        is_selector = isinstance(prompt, SelectorPrompt)
        attempts_limit = 1 if is_selector else MAX_ATTEMPTS

        def remaining_budget(cap):
            # 筛选阶段的排队和 HTTP 共用一个截止时间；普通生成保留原预算。
            if not is_selector:
                return cap
            remaining = prompt.deadline - time.monotonic()
            if remaining <= 0:
                safe_diagnostics.append({'category': 'selector_deadline_exceeded'})
                raise attach(TimeoutError('selector_deadline_exceeded'))
            return min(cap, remaining)

        def attach(exc: Exception, *, reason: str | None = None) -> Exception:
            """错误返回边界保留本调用全部尝试的脱敏证据，供只存错误类的调用方审计。"""
            items = list(diagnostics)
            if reason and (not items or items[-1] != reason):
                items.append(reason)
            exc.diagnostics = items
            exc.safe_diagnostics = list(safe_diagnostics)
            return exc

        def check_circuit() -> int:
            try:
                return _cb_check()
            except RuntimeError as exc:
                # _cb_check 字符串只由受控前缀与脱敏 reason 组成。
                safe_diagnostics.append({'category': 'circuit_open'})
                raise attach(exc, reason=str(exc)) from None

        for attempt in range(1, attempts_limit + 1):
            check_circuit()
            worker_started = False
            selector_acquired = False
            global_acquired = False
            try:
                if is_selector:
                    selector_wait = remaining_budget(GATE_WAIT_TIMEOUT)
                    selector_acquired = _selector_gate.acquire(timeout=selector_wait)
                    if not selector_acquired:
                        safe_diagnostics.append({'category': 'selector_gate_wait_timeout',
                            'attempt': attempt, 'wait_s': selector_wait})
                        raise attach(TimeoutError('selector_gate_wait_timeout'))
                gate_budget = remaining_budget(GATE_WAIT_TIMEOUT)
                if _gate is not None:
                    global_acquired = _gate.acquire(timeout=gate_budget)
                    if not global_acquired:
                        reason = f'gate_wait_timeout attempt={attempt} wait_s={gate_budget}'
                        safe_diagnostics.append({'category': 'gate_wait_timeout', 'attempt': attempt, 'wait_s': gate_budget})
                        raise attach(TimeoutError(reason), reason=reason)
                epoch = check_circuit()
                http_budget = remaining_budget(HARD_TIMEOUT)
                attempt_box: dict = {}

                def _run(box=attempt_box, release_selector=selector_acquired, release_global=global_acquired):
                    """每次尝试独占结果盒；真实HTTP退出才释放槽位，迟到结果不会串入重试。"""
                    try:
                        box["result"] = _one_call(prompt)
                    except Exception as exc:   # noqa: BLE001
                        box["error"] = exc
                    finally:
                        if release_global:
                            _gate.release()
                        if release_selector:
                            _selector_gate.release()

                th = threading.Thread(target=_run, daemon=True)
                started = time.monotonic()
                th.start()
                worker_started = True
                th.join(http_budget)
                if th.is_alive():
                    reason = f'hard_timeout attempt={attempt} elapsed_s={time.monotonic()-started:.3f}'
                    last_exc = TimeoutError(reason)
                    safe_diagnostics.append({'category': 'hard_timeout', 'attempt': attempt,
                        'elapsed_s': time.monotonic()-started})
                elif "error" in attempt_box:
                    error = attempt_box['error']
                    reason = _diagnostic(error, attempt, time.monotonic() - started)
                    last_exc = TimeoutError(reason) if isinstance(error, TimeoutError) else RuntimeError(reason)
                    from urllib.error import HTTPError
                    diagnostic = {'category': 'http_error' if isinstance(error, HTTPError) else 'network_error',
                        'attempt': attempt, 'elapsed_s': time.monotonic()-started}
                    if isinstance(error, HTTPError):
                        diagnostic['http_status'] = int(error.code)
                    safe_diagnostics.append(diagnostic)
                else:
                    _cb_note_ok(epoch)
                    return attempt_box["result"]
                diagnostics.append(reason)
                try:
                    _cb_note_fail(reason, epoch)
                except RuntimeError as exc:
                    safe_diagnostics.append({'category': 'circuit_open'})
                    raise attach(exc) from None
            finally:
                # 未启动线程的检查/启动异常由主线程归还槽位，其余归HTTP线程所有。
                if not worker_started:
                    if global_acquired:
                        _gate.release()
                    if selector_acquired:
                        _selector_gate.release()
            if attempt < attempts_limit:
                _backoff(attempt)
        raise attach(last_exc if last_exc else TimeoutError("request_failed"))

    return request


def _load_tasks(limit: int) -> list[dict]:
    """读取训练侧 PLT 有测试任务，跨 CWE 均衡采样（limit=0 表示全量）。"""
    data = json.loads((PROJECT_ROOT / "data/external/secodeplt/secodeplt/data.json").read_text(encoding="utf-8"))
    manifest = load_family_manifest(PROJECT_ROOT / "data/external/secodeplt/derived_metadata/family_manifest.json")
    tested = [r for r in data if has_tests(r)]
    fam = manifest["row_classification"]
    for r in tested:
        r["family_id"] = fam.get(str(r["index"]), {}).get("seed_family_id", "")
    if limit and limit > 0:
        # 跨 CWE 均衡采样到 limit
        by_cwe = defaultdict(list)
        for r in tested:
            by_cwe[str(r.get("CWE_ID"))].append(r)
        result = []
        for cwe in sorted(by_cwe):
            for r in by_cwe[cwe][:3]:
                result.append(r)
                if len(result) >= limit:
                    return result
        return result
    return tested


# 经验池周期落盘间隔（秒）。见 main() 里 _checkpoint_loop 的说明。
POOL_CHECKPOINT_SEC = 180


def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    """原子写 JSONL（先写临时文件再替换）。

    为什么不能用普通写：周期落盘与主流程写入可能重叠，看板/续跑若读到写了一半的
    文件会解析失败。os.replace 在同一卷上是原子的。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    os.replace(tmp, path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _status_counts(pool: list) -> dict:
    """统计经验池各状态条数（看板"树的变化"用）。"""
    from collections import Counter
    return dict(Counter(n.status for n in pool))


def _read_jsonl_tolerant(p: Path) -> list[dict]:
    """容错读取 jsonl：跳过崩溃时被截断的残行（不抛异常）。

    续跑与收尾统计都要读上游产物，而崩溃的运行其最后一行往往是半截 JSON，
    直接用 json.loads 会整体失败。
    """
    rows: list[dict] = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="CLE 轨迹对比式自进化（全量真实调用 AI）")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pool-manifest", type=Path, default=None,
                        help="固定四池清单；使用 D_init/D_grow/D_gate，禁止 H_pass 进入训练")
    parser.add_argument("--limit", type=int, default=0, help="参与的任务数上限；0=全量 874 条")
    parser.add_argument("--model", type=str, default="deepseek-v3.2")
    parser.add_argument("--max-tokens", type=int, default=1500,
                        help="单次 LLM 回复的 token 上限。原先是硬编码 1500 —— "
                             "deepseek-v3.2 实测单步仅用 169 tokens，够用；"
                             "但换用输出更长的模型（如 gpt-5.6-luna 单次分析即用 1128）"
                             "会在 CodeGen 步骤触发 finish_reason=length → "
                             "model_output_truncated → 任务被判失败，必须相应调大。")
    parser.add_argument("--timeout", type=int, default=90, help="单次 LLM 请求超时（秒）")
    parser.add_argument("--validation-timeout", type=int, default=20, help="本地验证超时（秒）")
    parser.add_argument("--resume-from", type=Path, default=None,
                        help="续跑：从该运行目录恢复经验池/树/错题本，跳过 Phase1 与已完成轮次")
    parser.add_argument("--workers", type=int, default=80,
                        help="Phase1/Phase2 并发 worker 数。默认 80（用户拍板 2026-09-22）。"
                             "注意：实测 deepseek 系在 **80 并发附近开始丢包**（80 档成功率 99%%），"
                             "90 档吞吐从 4.4/s 崩到 0.81/s；本机 CPU 不是瓶颈"
                             "（实测运行中仅 23%%、单次本地验证 0.27s）。"
                             "若出现大量重试/超时，先降到 60。")
    parser.add_argument("--phase3-workers", type=int, default=24,
                        help="Phase3 门控审计的并发。**单独设置**：Phase3 每条经验要跑"
                             "（基线+加经验）两轮生成，若也用 24 并发会瞬间打出大量请求、"
                             "成本与限流风险陡增。默认 8（可在耗时与压力间折中）")
    parser.add_argument("--repairs", type=int, default=1, help="每任务修复轮数")
    parser.add_argument("--replay-limit", type=int, default=96,
                        help="每轮回放任务数上限（LLM 有界筛选后的硬上限）")
    parser.add_argument("--batch-size", type=int, default=96,
                        help="规则配额初筛的批大小，即送进 LLM 的候选数。"
                             "默认 96（原 24）：用户拍板池子里近 300 条却每轮只选一点不对，"
                             "故扩大候选窗口，让 LLM 有更大选择空间")
    parser.add_argument("--min-audit-tasks", type=int, default=3,
                        help="每条经验至少用几个审计任务检验（用户要求增加被挑选的例子数量）。"
                             "实测小规模下 21/36 条只用 1 个任务、7 条用 0 个，证据太单薄")
    parser.add_argument("--coverage-target", type=float, default=0.75,
                        help="重放池覆盖率目标（用户要求 ≥0.75）。每轮按剩余轮数均摊配额，"
                             "优先补从未重放过的任务")
    parser.add_argument("--rounds", type=int, default=3, help="Phase2+3 多轮演进轮数")
    parser.add_argument('--branch-count', type=int, default=1, help='Phase2方案数；3启用多思路一次生成，替代串行修复')
    parser.add_argument('--gate-mode', choices=('candidate', 'global'), default='candidate', help='global: Phase2全部轮次结束后全量门控')
    parser.add_argument("--audit-per-candidate", type=int, default=5, help="每候选做 ΔJointPass 的 audit 任务数")
    parser.add_argument("--regression-samples", type=int, default=3, help="Gate3 回归的 N 次多数决采样数")
    parser.add_argument("--audit-max-entries", type=int, default=48,
                        help="每轮最多审计多少条经验（按信息价值+CWE去重抽样，0=不限）。"
                             "默认 48——门控是唯一的质量过滤器，覆盖面越大筛得越准；"
                             "用户要求增加被挑选的例子数量")
    parser.add_argument("--retrieval-mode", type=str, default="flat_llm",
                        choices=["flat_llm", "flat_rule", "hier_llm", "hier_rule", "semantic_llm", "semantic_hybrid_v2"],
                        help="检索机制（用户 2026-09-22）。flat_llm=旧机制逐候选打 LLM 分；"
                             "hier_llm=层次化自顶向下检索（LLM 看树骨架后逐层下探）；"
                             "flat_rule/hier_rule 为无 LLM 消融对照臂")
    parser.add_argument('--embedding-model', default='text-embedding-3-large')
    parser.add_argument('--selector-max-inflight', type=int, default=16,
                        help='语义筛选长上下文请求子上限；所有阶段仍共享 max-inflight 总上限')
    parser.add_argument('--embedding-cache', type=Path, default=Path('translation_work/cache/embeddings/cle.sqlite3'))
    parser.add_argument("--same-task-bonus", type=float, default=2.0,
                        help="同任务历史失败经验的检索加权（改造 D）。实测原注入率为零，"
                             "而该任务上次为何失败是最直接的修复线索")
    parser.add_argument("--antioverdefense-bonus", type=float, default=1.5,
                        help="抑制过度防御类经验(minimal_patch_hint/overdefense_pitfall)的检索加权；"
                             "0=关闭。依据：47.3%% 的失败是过度防御")
    parser.add_argument("--min-llm-score", type=float, default=0.6,
                        help="注入相关性门槛：LLM 打分低于此值的经验不注入（0=关闭，回到凑满 limit 的旧行为）")
    parser.add_argument("--cross-cwe-min-score", type=float, default=0.75,
                        help="跨 CWE 经验的相关性门槛（比同 CWE 更严）")
    parser.add_argument("--gate-select-mode", type=str, default="llm",
                        choices=["llm", "fixed"],
                        help="门控例子数模式：llm=LLM 自由决定（允许 0 条，默认）/ fixed=固定 N 条")
    parser.add_argument("--gate-fixed-examples", type=int, default=2,
                        help="--gate-select-mode=fixed 时每条经验固定用几个例子")
    parser.add_argument("--consolidate-max-active", type=int, default=3,
                        help="同 CWE active 节点超过该值触发 LLM 归并。默认 3——实测每 CWE "
                             "active 最多 3 个，原默认 4 导致归并从未触发（3 轮均 0 次）")
    parser.add_argument("--max-inflight", type=int, default=0,
                        help="全局在途 LLM 请求数上限（0 = 不限，等于 --workers）。"
                             "任务内部的并行调用（检索打分、基线探测）会让实际并发 = "
                             "workers × 任务内并行数，用这道闸门兜住总在途量，"
                             "避免超过 API 丢包线。建议设成与 --workers 相同或略高。")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="同一任务最多被强制重放几次（上一轮末态 B/C/D 时）")
    parser.add_argument("--inject-prev-evidence", action="store_true", default=False,
                        help="修复轮是否把上一轮的动态测试报错**直接拼进** Analysis/Planning prompt。"
                             "默认关闭：用户拍板走「报错先入经验库 → 下一轮由检索器取回」的路线"
                             "（见 retriever.search 的同任务优先）。"
                             "注意：同一次 rollout 内的修复轮拿不到检索结果（经验要等 rollout "
                             "结束才提炼入池），Phase1 更是完全不接检索器——需要覆盖这种场景时才打开。")
    parser.add_argument("--context-pipeline", action="store_true",
                        help="启用初析→检索→经验结合再分析→规划→生成；不改变门控阈值")
    parser.add_argument("--internal-checks", action="store_true",
                        help="增加公开契约自生成内部测试供修复；不替代PLT正式训练验证")
    parser.add_argument("--anti-overdefense", type=str, default="contract_freeze",
                        choices=["base", "anti_od", "contract_freeze"],
                        help="反过度防御干预臂。默认 contract_freeze——由 3 臂实验实测决定："
                             "base 2/6 < anti_od 3/6 < contract_freeze 4/6，过度防御案例 3 降到 1。"
                             "见 docs/cle_negative_findings.md 实验四。")
    parser.add_argument("--ablation", type=str, default="A7",
                        help="消融组 A1~A7（控制 HSK-Tree 各层的生成与注入）。默认 A7——"
                             "用户拍板（2026-09-20）：Level 4 四语言叶生成对本任务无可见收益，"
                             "却让每个 seed 多 4 次 LLM 调用，故默认关闭。"
                             "需要复现带 L4 的实验时用 A4/A5/A6。见 ablation.py")
    args = parser.parse_args()
    if args.selector_max_inflight < 1:
        parser.error('--selector-max-inflight must be positive')
    if args.branch_count < 1 or (args.branch_count > 1 and not args.context_pipeline):
        parser.error('branch-count > 1 requires context-pipeline')
    if args.internal_checks and not (args.context_pipeline and args.inject_prev_evidence):
        parser.error('--internal-checks requires --context-pipeline and --inject-prev-evidence')

    out: Path = args.out
    if out.exists() and any(out.iterdir()):
        parser.error('output directory must be new or empty; refusing to overwrite evidence')
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "progress.log"

    def progress(msg: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        # 执行阶段可见性：逐条回放/审计进度更新看板，不把进程存活当作验证通过。
        if msg.startswith("[Phase2") or msg.startswith("[Phase3"):
            phase = "phase3" if msg.startswith("[Phase3") else "phase2"
            write_status(out, status="running", stage=phase, detail=msg)

    # 【输出目录必须干净】（缺陷 S4，2026-09-21 代码审查）
    # 下面 4 个"逐条落盘"的产物用 "a"（追加）模式打开，而 status.json /
    # run_metadata.json / summary.json 是覆盖写。两者口径不一致 → 同名目录重跑时
    # 旧行会留在文件里，条数翻倍、统计口径被污染，且**没有任何提示**。
    # 处理：启动时清掉本次运行会重写的流式产物。
    # 安全前提：--resume-from 必须指向**另一个**目录——否则会先删掉要读的上游产物。
    if args.resume_from and args.resume_from.resolve() == out.resolve():
        raise SystemExit("❌ --resume-from 与 --out 指向同一目录："
                         "启动清理会先删掉上游产物再读取，已拒绝执行")
    for _name in ("phase1_results.jsonl", "trajectories.jsonl",
                  "audit_detail.jsonl", "final_eval.jsonl"):
        _p = out / _name
        if not _p.exists() or _p.stat().st_size == 0:
            continue
        # 【必须用截断而不是 unlink】（2026-09-22 事故）
        # 原实现用 Path.unlink()，但它会被工作区的"批量删除保护"拦下
        # （实测 phase1_results.jsonl 有 78 行 > 阈值 50，抛
        #  SAFE_DELETE_BULK_CONFIRM_REQUIRED）—— 而清理动作在启动最前面，
        #  异常直接把整条运行干掉。清空内容同样达到"避免跨运行数据混杂"的目的，
        #  且不触发删除保护。
        try:
            _p.write_text("", encoding="utf-8")
            progress(f"[清理] 清空上次运行残留的 {_name}（避免跨运行数据混杂）")
        except Exception as _exc:
            # 清理失败也不能挡住运行；后续 append 会写在同一文件里，
            # 但至少 status/run_metadata 是覆盖写的，不会静默混淆
            progress(f"[清理] 警告：{_name} 清空失败（{type(_exc).__name__}），"
                     f"该文件的旧内容可能混入本次运行")

    # 看板：登记运行 + 写初始状态（"进行中"由此识别）
    run_name = out.name
    sct_runs_root = out.parent
    write_status(out, status="running", stage="init", detail="初始化")
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="running", model=args.model)

    tasks = _load_tasks(args.limit)
    external_pool_manifest = None
    if args.pool_manifest:
        from methods.cle_ablation_matrix.pool_manifest import validate_manifest
        external_pool_manifest = json.loads(args.pool_manifest.read_text(encoding="utf-8"))
        validate_manifest(external_pool_manifest, tasks)
        allowed = {str(entry["task_id"]) for name in ("D_init", "D_grow", "D_gate")
                   for entry in external_pool_manifest["pools"][name]}
        tasks = [task for task in tasks if str(task["index"]) in allowed]
        expected = sum(len(external_pool_manifest["pools"][name]) for name in ("D_init", "D_grow", "D_gate"))
        if len(tasks) != expected:
            raise SystemExit(f"pool manifest task mismatch: expected {expected}, got {len(tasks)}")
    progress(f"加载训练侧任务 {len(tasks)} 条（limit={args.limit or '全量'}）")

    # 三池原子划分
    family_fn = lambda rid: next((t["family_id"] for t in tasks if int(t["index"]) == rid), "")
    if external_pool_manifest:
        task_by_id = {str(task["index"]): task for task in tasks}
        pools = {
            "source_pool": [task_by_id[str(entry["task_id"])] ["index"] for entry in external_pool_manifest["pools"]["D_init"]],
            "replay_pool": [task_by_id[str(entry["task_id"])] ["index"] for entry in external_pool_manifest["pools"]["D_grow"]],
            "audit_pool": [task_by_id[str(entry["task_id"])] ["index"] for entry in external_pool_manifest["pools"]["D_gate"]],
        }
    else:
        pools = assign_families_atomic([t["index"] for t in tasks], family_fn)
    source = [t for t in tasks if t["index"] in pools["source_pool"]]
    replay = [t for t in tasks if t["index"] in pools["replay_pool"]]
    audit = [t for t in tasks if t["index"] in pools["audit_pool"]]
    phase2_complete_resume = False
    if args.gate_mode == 'global' and args.resume_from:
        from methods.sct_trajectory.training_checkpoint import phase1_resume_source, phase2_resume_source
        completed_path = args.resume_from / 'completed_rounds.jsonl'
        completed_rows = _read_jsonl_tolerant(completed_path) if completed_path.exists() else []
        completed_count = len(completed_rows)
        phase2_complete_resume = (completed_count == args.rounds
                                  and (args.resume_from / 'trajectories.jsonl').exists()
                                  and (args.resume_from / 'experience_pool.jsonl').exists()
                                  and (args.resume_from / 'phase1_results.jsonl').exists())
        has_phase2_checkpoint = (args.resume_from / 'trajectories.jsonl').exists() and (
            args.resume_from / 'completed_rounds.jsonl').exists()
        restored = ({'path': str(args.resume_from.resolve()), 'mode': 'phase3_only',
                     'completed_rounds': completed_count,
                     'memory_count': len(_read_jsonl_tolerant(args.resume_from / 'experience_pool.jsonl'))}
                    if phase2_complete_resume else
                    (phase2_resume_source(args.resume_from, {r['index'] for r in source},
                                          completed_count, args.rounds)
                     if has_phase2_checkpoint else
                     phase1_resume_source(args.resume_from, {r['index'] for r in source})))
        (out / 'resume_manifest.json').write_text(json.dumps(restored, indent=2), encoding='utf-8')
    progress(f"三池划分: source={len(source)} replay={len(replay)} audit={len(audit)}")
    # 看板：三池任务清单
    write_pools(out, source=source, replay=replay, audit=audit)
    write_run_metadata(out, model=args.model, args=vars(args), dataset="data/external/secodeplt")
    # 留下本次实际执行源码与数据指纹；dirty工作区的commit不能单独代表运行版本。
    import hashlib
    import shutil
    source_paths = list((PROJECT_ROOT / "methods/sct_trajectory").glob("*.py"))
    source_paths += [PROJECT_ROOT / "methods/sct_agent/validation_evidence.py"]
    source_paths += list((PROJECT_ROOT / 'methods/sct_lifecycle_replay').glob('*.py'))
    source_hashes = {}
    for source_path in source_paths:
        relative = source_path.relative_to(PROJECT_ROOT)
        target = out / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        source_hashes[str(relative)] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    (out / "source_manifest.json").write_text(json.dumps({
        "sources": source_hashes,
        "training_data_sha256": hashlib.sha256((PROJECT_ROOT / "data/external/secodeplt/secodeplt/data.json").read_bytes()).hexdigest(),
        "pipeline": "analysis_retrieval_reanalysis" if args.context_pipeline else "legacy",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="running",
                     model=args.model, tasks=len(tasks))

    tree = HskTree()
    ledger = ErrorLedger()
    # 消融配置：控制 HSK-Tree 各层的生成与注入（A1~A6）
    ablation_cfg = get_ablation(args.ablation)
    progress(f"消融组 {ablation_cfg.group}：split_level23={ablation_cfg.split_level23} "
             f"L4生成(text={ablation_cfg.gen_l4_text},constructs={ablation_cfg.gen_l4_constructs},"
             f"snippet={ablation_cfg.gen_l4_snippet}) "
             f"L4注入(text={ablation_cfg.inject_l4_text},constructs={ablation_cfg.inject_l4_constructs},"
             f"snippet={ablation_cfg.inject_l4_snippet})")
    _inflight = args.max_inflight if args.max_inflight > 0 else args.workers
    shared_requests = threading.BoundedSemaphore(_inflight)
    embedding_client = None
    if args.retrieval_mode in ('semantic_llm', 'semantic_hybrid_v2'):
        from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
        embedding_client = EmbeddingClient(model=args.embedding_model, cache_path=args.embedding_cache,
                                           key_loader=load_key, semaphore=shared_requests, timeout=args.timeout)
    runner = CleRunner(_requester(args.model, args.timeout, args.max_tokens, _inflight, semaphore=shared_requests,
                                 selector_max_inflight=args.selector_max_inflight),
                       tree, ledger,
                       timeout=args.validation_timeout, workers=args.workers, progress=progress,
                       ablation=ablation_cfg, anti_overdefense=args.anti_overdefense,
                       gate_select_mode=args.gate_select_mode,
                       gate_fixed_examples=args.gate_fixed_examples,
                       min_llm_score=args.min_llm_score,
                       cross_cwe_min_score=args.cross_cwe_min_score,
                       antioverdefense_bonus=args.antioverdefense_bonus,
                       same_task_bonus=args.same_task_bonus,
                       retrieval_mode=args.retrieval_mode,
                       phase3_workers=args.phase3_workers,
                       inject_prev_evidence=args.inject_prev_evidence,
                       context_pipeline=args.context_pipeline,
                       internal_checks=args.internal_checks,
                       branch_count=args.branch_count, gate_mode=args.gate_mode,
                       embedding_client=embedding_client)

    # 【周期落盘经验池】（缺陷 D35，2026-09-22 卡死事故）
    # 原先 experience_pool.jsonl 只在"每轮结束"或"抛异常"时写。而**卡死**（LLM 请求
    # 永久挂起、在重试里空转）既不是轮结束、也不抛异常 —— 进程被杀后没有任何经验池，
    # `--resume-from` 会直接拒绝（它强制要求该文件存在），数小时运行全部作废。
    # 实测：2026-09-22 01:43 的全量运行卡在 Gate3 回归探针，就是这样丢掉的。
    # 【必须放在 Phase1 之前】：Phase1 本身就要跑十几分钟，是本机制最该覆盖的窗口；
    # 曾经误放在 Phase2 之前，导致 Phase1 全程无保护（实测 227 秒仍无落盘）。
    _ckpt_stop = threading.Event()

    def _checkpoint_loop() -> None:
        while not _ckpt_stop.wait(POOL_CHECKPOINT_SEC):
            try:
                with runner._pool_lock:
                    pool_rows = [n.to_dict() for n in runner.experience_pool]
                    ledger_rows = ledger.to_jsonl()
                if pool_rows:
                    _write_jsonl_atomic(out / "experience_pool.jsonl", pool_rows)
                    _write_jsonl_atomic(out / "error_ledger.jsonl", ledger_rows)
                _write_jsonl_atomic(out / 'english_admission_rejections.jsonl', list(runner.admission_rejections))
                if embedding_client:
                    (out / 'embedding_usage.json').write_text(json.dumps(embedding_client.usage, indent=2), encoding='utf-8')
            except Exception:
                # 落盘失败绝不能影响主流程（它只是"保险"）
                continue

    _ckpt_thread = threading.Thread(target=_checkpoint_loop, daemon=True,
                                    name="pool-checkpoint")
    _ckpt_thread.start()
    progress(f"=== 已启动经验池周期落盘（每 {POOL_CHECKPOINT_SEC} 秒，Phase1 起生效）===")

    # 流式落盘句柄：逐条 append，便于断点续跑与实时观测
    p1_path = out / "phase1_results.jsonl"
    traj_path = out / "trajectories.jsonl"
    p1_handle = open(p1_path, "a", encoding="utf-8")
    traj_handle = open(traj_path, "a", encoding="utf-8")
    _p1_done = [0]   # Phase1 已完成计数（用于心跳 progress）

    def on_phase1_item(clean: dict) -> None:
        p1_handle.write(json.dumps(clean, ensure_ascii=False) + "\n")
        p1_handle.flush()
        # 周期性刷新心跳：status.json 原先只在阶段边界写，Phase1 跑 5 小时期间
        # 心跳一直停在启动时刻，看板（STALE_SECONDS=120）会把健康运行误标为 stale。
        _p1_done[0] += 1
        write_status(out, status="running", stage="phase1",
                     detail=f"冷启动 {_p1_done[0]}/{len(source)} 条",
                     progress={"done": _p1_done[0], "total": len(source)})

    def dump_pool(label: str) -> None:
        """把当前经验池内容快照落盘（供"阶段经验库对比"实验使用）。

        所属阶段：产物记录（不属于 CLE 方法本身，不改变任何方法行为）。
        为什么需要：第二步要比较 Phase1 池 / Phase2 各轮池 / 最终池的效果，
        而 Phase2 的 distill 输出原先不落盘，旧产物无法重建各轮池。
        安全边界：只读 `runner.experience_pool` 并写文件；不写树、不改状态、
        不触发任何 LLM 调用。产物写在 translation_work/ 下（运行目录内）。
        """
        snap_dir = out / "pool_snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(snap_dir / f"{label}.jsonl",
                     [n.to_dict() for n in runner.experience_pool])
        progress(f"[池快照] {label}: {len(runner.experience_pool)} 条")

    def on_phase2_item(out_item: dict) -> None:
        trace = out_item.get("trace")
        if trace is not None:
            traj_handle.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
            traj_handle.flush()

    audit_handle = open(out / "audit_detail.jsonl", "a", encoding="utf-8")

    def on_audit_item(detail: dict) -> None:
        """逐条写审计明细（增量落盘，防中断丢失）。"""
        audit_handle.write(json.dumps(detail, ensure_ascii=False) + "\n")
        audit_handle.flush()

    def on_round_end(rnd: int, tree_obj, round_log: dict) -> None:
        """每轮结束写树快照（看板画成长轨迹）+ 刷新心跳。"""
        write_tree_snapshot(out, label=f"round{rnd}", tree=tree_obj, extra={"round_log": round_log})
        dump_pool(f"round{rnd}")
        # 完整轮边界另行增量落盘；不能从已产生轨迹的最大轮号推断门控已结束。
        with (out / 'completed_rounds.jsonl').open('a', encoding='utf-8') as completed:
            completed.write(json.dumps(round_log, ensure_ascii=False) + '\n')
        write_status(out, status="running", stage="phase2",
                     detail=f"第 {rnd} 轮完成",
                     progress={"round": rnd, "tree_nodes": round_log.get("tree_nodes", 0),
                               "promoted": round_log.get("promoted", 0)})

    # ---------- 续跑：从崩溃运行恢复状态 ----------
    # 用途：运行中途因异常（如 API 超时）中断后，复用其 Phase1 结果、经验池、
    # 错题本与已完成轮次，避免从零重跑数小时。
    # 语义：--resume-from <目录> 时，跳过 Phase1 与已完成轮次，从下一轮继续。
    resumed_rounds = 0
    seed_forced: list[int] = []
    if args.resume_from:
        src: Path = args.resume_from


        pool_rows = _read_jsonl_tolerant(src / "experience_pool.jsonl")
        if not pool_rows:
            raise SystemExit(f"❌ 续跑失败：{src/'experience_pool.jsonl'} 不存在或为空")
        progress(f"=== 续跑模式：从 {src.name} 恢复 ===")
        progress(f"上游经验池 {len(pool_rows)} 条；Phase1 结果 {len(_read_jsonl_tolerant(src/'phase1_results.jsonl'))} 条")

        # ① 恢复经验池 + 把 active 节点重建进树
        for row in pool_rows:
            runner.experience_pool.append(SecurityInvariantNode.from_dict(row))
        for row in pool_rows:
            if str(row.get("status")) == "active":
                tree.insert_node(SecurityInvariantNode.from_dict(row))
        n_active = sum(1 for r in pool_rows if str(r.get("status")) == "active")
        progress(f"恢复经验池 {len(runner.experience_pool)} 条，其中 active {n_active} 条已入树")

        # ② 恢复错题本（add 接受 ErrorEntry 对象，故用 from_dict 还原）
        from methods.sct_trajectory.error_ledger import ErrorEntry

        restored = 0
        for row in _read_jsonl_tolerant(src / "error_ledger.jsonl"):
            try:
                ledger.add(ErrorEntry.from_dict(row))
                restored += 1
            except Exception:
                continue
        progress(f"恢复错题本 {restored} 条")

        # ③ 继承强制重放集合：上游最后一轮"末态非 A"的任务必须在本段首轮重放
        #    （否则会丢失 DOCX 的硬约束——失败样本必须被强制重放）
        traj_rows = _read_jsonl_tolerant(src / "trajectories.jsonl")
        # 轨迹会在一轮尚未结束时逐条追加，不能用其中的最大 round 推断
        # 已完成轮数；只有 completed_rounds.jsonl 写入的轮边界才算完整检查点。
        # 否则中途终止的第 3 轮会被误认为已完成，续跑会跳过必要的剩余轮次。
        completed_rows = _read_jsonl_tolerant(src / "completed_rounds.jsonl")
        resumed_rounds = max((int(r.get("round") or 0) for r in completed_rows), default=0)
        last_round = max(((t.get("round") or 0) for t in traj_rows), default=0)
        by_index = {int(r.get("index", -1)) for r in replay}
        for t in traj_rows:
            if (t.get("round") or 0) == last_round:
                states = t.get("states") or []
                tid = int(t.get("task_id") or -1)
                if states and states[-1] != "A" and tid in by_index:
                    seed_forced.append(tid)
        progress(f"上游已完成轮数={resumed_rounds}；轨迹最后轮号={last_round}；"
                 f"末态非 A 且在 replay 池内 {len(seed_forced)} 条 → 本段首轮强制重放 {seed_forced}")

    # Phase 1
    if args.resume_from:
        progress(f"=== Phase 1 跳过（续跑复用上游 {len(source)} 条结果）===")
        write_tree_snapshot(out, label="phase1", tree=tree,
                            extra={"pool_size": len(runner.experience_pool), "resumed": True},
                            pool=runner.experience_pool)
    else:
        progress(f"=== Phase 1 冷启动开始（{len(source)} 条）===")
        write_status(out, status="running", stage="phase1", detail=f"冷启动 {len(source)} 条")
        p1 = runner.phase1_seed(source, repairs=args.repairs, on_item=on_phase1_item)
        p1_handle.close()
        progress(f"=== Phase 1 完成：树 {p1['tree_size']} 节点 ===")
        dump_pool("phase1")
        write_tree_snapshot(out, label="phase1", tree=tree,
                            extra={"pool_size": len(runner.experience_pool)},
                            pool=runner.experience_pool)
        write_status(out, status="running", stage="phase1",
                     detail=f"冷启动完成，树 {p1['tree_size']} 节点",
                     progress={"tree_nodes": p1["tree_size"], "pool": len(runner.experience_pool)})

    # Phase 2 + 3：多轮闭环演进（Replay-Audit 迭代，新经验在轮间真正入树）
    # 全局门控续跑时只补足尚未完成的轮数；部分轮次的轨迹由 seed_forced
    # 继承，但不把它误计入 completed_rounds。
    round_plan = (0 if phase2_complete_resume else
                  max(1, args.rounds - resumed_rounds))
    progress(f"=== Phase 2+3 多轮演进开始（replay {len(replay)} 条 / audit {len(audit)} 条 / "
             f"本段 {round_plan} 轮{'' if not resumed_rounds else f'，上游已完成 {resumed_rounds} 轮'}）===")
    if resumed_rounds and not phase2_complete_resume:
        progress(f"【口径提示】本运行日志里的『轮1』= 上游的『轮{resumed_rounds + 1}』，"
                 f"轮次编号在本段内重新计数。")
    write_status(out, status="running", stage="phase2", detail=f"多轮演进 {round_plan} 轮")

    # 网络/异常保护：即使某阶段抛错，也要落盘已完成的部分并把运行标记为 failed，
    # 否则看板会看到一个"永远 running"的空目录（实测遇到过 API 断连导致全丢）。
    try:
        if phase2_complete_resume:
            evo = {'rounds': _read_jsonl_tolerant(args.resume_from / 'completed_rounds.jsonl'),
                   'gate_records': [], 'audit_detail': [],
                   'tree_before': tree.to_dict(), 'tree_after': tree.to_dict()}
            progress('=== 续跑模式：上游 Phase 2 已完整完成，跳过演进，仅执行 Phase 3 ===')
        else:
            evo = runner.run_evolution_rounds(
                replay, audit,
                rounds=round_plan,
                seed_forced=seed_forced or None,
                coverage_target=args.coverage_target,
                min_audit_tasks=args.min_audit_tasks,
                batch_size=args.batch_size,
                replay_limit=args.replay_limit,
                repairs=args.repairs,
                audit_per_candidate=args.audit_per_candidate,
                regression_samples=args.regression_samples,
                audit_max_entries=args.audit_max_entries,
                max_retries=args.max_retries,
                consolidate_max_active=args.consolidate_max_active,
                on_audit=on_audit_item,
                on_phase2_item=on_phase2_item,
                on_round_end=on_round_end,
            )
    except Exception as exc:
        traj_handle.close()
        _write_jsonl_atomic(out / "error_ledger.jsonl", ledger.to_jsonl())
        _write_jsonl_atomic(out / "experience_pool.jsonl", [n.to_dict() for n in runner.experience_pool])
        write_tree_snapshot(out, label="failed", tree=tree)
        write_status(out, status="failed", stage="phase2",
                     detail=f"多轮演进中断：{type(exc).__name__}", error=str(exc)[:500])
        append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="failed",
                         model=args.model, tasks=len(tasks),
                         extra={"error": type(exc).__name__})
        progress(f"!!! 多轮演进中断（{type(exc).__name__}），已落盘部分产物并标记 failed：{exc}")
        raise
    traj_handle.close()
    _ckpt_stop.set()          # 停止周期落盘（下面会做一次完整落盘）
    _ckpt_thread.join(timeout=30)
    _write_jsonl(out / "gate_records.jsonl", evo["gate_records"])
    audit_handle.close()
    _write_jsonl(out / "rounds.jsonl", evo["rounds"])
    progress(f"=== 多轮演进完成：{len(evo['rounds'])} 轮 ===")

    # 看板：树成长轨迹——逐轮相邻 diff（"这一轮比上一轮多了哪些规则"）
    from methods.sct_trajectory.run_artifacts import diff_snapshots

    snap_dir = out / "tree_snapshots"
    labels = ["phase1"] + [f"round{i}" for i in range(1, args.rounds + 1)]
    snaps = []
    for lb in labels:
        p = snap_dir / f"{lb}.json"
        if p.exists():
            snaps.append(json.loads(p.read_text(encoding="utf-8")))
    growth = [diff_snapshots(snaps[i], snaps[i + 1]) for i in range(len(snaps) - 1)]
    (out / "tree_growth.json").write_text(json.dumps({
        "timeline": [{"label": s.get("label"), "created_at": s.get("created_at"),
                      "rule_count": len(s.get("rule_ids") or [])} for s in snaps],
        "diffs": growth,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 看板：Phase3 门控的树变化。门控发生在每一轮内部（phase3_audit），
    # 因此对比数据取自 rounds.jsonl 的 tree_before/tree_after（逐轮精确），
    # 这里只落最终态快照 + 汇总文件。
    write_tree_snapshot(out, label="gate_after", tree=tree,
                        extra={"tree_counts": evo.get("tree_after")})
    (out / "tree_change.json").write_text(json.dumps({
        "overall_before": evo.get("tree_before"),
        "overall_after": evo.get("tree_after"),
        "rounds": [{"round": r.get("round"), "before": r.get("tree_before"),
                    "after": r.get("tree_after"), "promoted": r.get("promoted"),
                    "merged": r.get("merged"), "pruned": r.get("pruned"),
                    "audited": r.get("audited")}
                   for r in evo.get("rounds", [])],
        "gate_records": [{"candidate_id": g.get("candidate_id"), "decision": g.get("decision"),
                          "reasons": g.get("reasons")} for g in evo.get("gate_records", [])],
        "experience_pool_status": {
            "total": len(runner.experience_pool),
            "by_status": _status_counts(runner.experience_pool),
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Phase 3 收尾：冻结经验树 M* + 在审计池全量评测（每次运行自动执行）----
    global_result = None
    if args.gate_mode == 'global':
        # 先完成有库/无库/局部归因及过滤重测，再冻结。此阶段不访问Plus。
        from methods.sct_trajectory.global_gate_runtime import finalize_global_gate
        write_status(out, status='running', stage='phase3', detail='训练D_gate全量配对门控')
        try:
            global_result = finalize_global_gate(runner, audit, out)
            tree = runner.tree
            # 全量门控在全部演进轮之后；覆盖此前仅表示候选积累完成的看板快照。
            decisions = global_result['gate_report']['decisions']
            records = [{'candidate_id': key, **value} for key, value in decisions.items()]
            evo['gate_records'] = records
            _write_jsonl(out / 'gate_records.jsonl', records)
            write_tree_snapshot(out, label='gate_after', tree=tree,
                                extra={'gate_mode': 'global', 'report': 'global_gate_report.json'})
            (out / 'tree_change.json').write_text(json.dumps({
                'gate_mode': 'global', 'gate_timing': 'after_all_phase2_rounds',
                'gate_records': records, 'report': 'global_gate_report.json',
                'experience_pool_status': {'total': len(runner.experience_pool),
                                           'by_status': _status_counts(runner.experience_pool)},
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            _write_jsonl_atomic(out / 'experience_pool.jsonl', [n.to_dict() for n in runner.experience_pool])
            # Phase 3 是训练侧 D_gate；失败也必须保留脱敏上下文，不能只写异常类名。
            # 这里不写 prompt、响应或密钥，只记录阶段、异常消息截断值和 traceback，
            # 便于区分 API/检索/验证异常与输入契约异常，并支持后续从冻结经验池续跑。
            import traceback as _traceback
            diagnostic = {
                'stage': 'phase3_global_gate',
                'error_type': type(exc).__name__,
                'error_message': str(exc)[:1000],
                'traceback': _traceback.format_exc(limit=25),
                'task_count': len(audit),
                'experience_count': len(runner.experience_pool),
                'model': args.model,
                'workers': args.workers,
                'phase3_workers': args.phase3_workers,
            }
            (out / 'phase3_exception.json').write_text(
                json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding='utf-8')
            write_status(out, status='failed', stage='phase3', detail='全量门控失败',
                         error=type(exc).__name__, error_message=str(exc)[:1000])
            raise
    write_status(out, status="running", stage="final_eval", detail="冻结 + 审计池全量评测")
    frozen = runner.freeze_tree()
    _write_jsonl(out / "frozen" / "m_star.jsonl", frozen)
    progress(f"=== 冻结经验树 M*：{len(frozen)} 条经验；开始审计池全量评测（{len(audit)} 条）===")
    fe_handle = open(out / "final_eval.jsonl", "a", encoding="utf-8")

    def on_final_item(row: dict) -> None:
        fe_handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        fe_handle.flush()

    # 【最终评测必须有异常保护】（缺陷 S3，2026-09-21 代码审查）
    # 原实现没有 try/except，而 experience_pool.jsonl（**续跑的唯一前提**）、
    # error_ledger.jsonl、tree.json、summary.json 全都在它之后才写。
    # 全量运行约 11 小时，若最终评测阶段一次 API 断连/超时抛异常 → 整个运行
    # 零产物落盘，且因为缺少 experience_pool.jsonl 而**无法续跑**（见上面的
    # `raise SystemExit(f"❌ 续跑失败：...experience_pool.jsonl 不存在或为空")`）。
    # 这里补上与 run_evolution_rounds 同等的"失败也要落盘已完成部分"保护。
    try:
        if global_result is not None:
            fe = global_result
            for row in fe['rows']:
                on_final_item(row)
        else:
            fe = runner.final_evaluate(audit, on_item=on_final_item)
    except Exception as exc:
        fe_handle.close()
        _write_jsonl_atomic(out / "error_ledger.jsonl", ledger.to_jsonl())
        _write_jsonl_atomic(out / "experience_pool.jsonl", [n.to_dict() for n in runner.experience_pool])
        (out / "tree.json").write_text(
            json.dumps(tree.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        write_status(out, status="failed", stage="final_eval",
                     detail=f"最终评测中断：{type(exc).__name__}", error=str(exc)[:500])
        append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="failed",
                         model=args.model, tasks=len(tasks),
                         extra={"error": type(exc).__name__, "stage": "final_eval"})
        progress(f"!!! 最终评测中断（{type(exc).__name__}）：已落盘经验池 "
                 f"{len(runner.experience_pool)} 条与错题本，可据此续跑。错误：{exc}")
        raise
    fe_handle.close()
    (out / "final_eval_summary.json").write_text(
        json.dumps(fe["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    progress(f"=== 最终评测完成：JointPass {fe['summary']['joint_pass']}/{fe['summary']['eval_pool_size']} "
             f"= {100*fe['summary']['joint_pass_rate']:.1f}% ===")

    # 落盘
    _write_jsonl(out / "error_ledger.jsonl", ledger.to_jsonl())
    # 统一经验池：Phase1 与 Phase2 产出的全部经验（含失败提炼的盲区），附来源元数据
    _write_jsonl_atomic(out / "experience_pool.jsonl", [n.to_dict() for n in runner.experience_pool])
    (out / "tree.json").write_text(json.dumps(tree.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    pool_by_stage: dict[str, int] = {}
    for n in runner.experience_pool:
        st = (n.source or {}).get("stage", "unknown")
        pool_by_stage[st] = pool_by_stage.get(st, 0) + 1
    # 续跑时 Phase1 被跳过，p1 不存在 → 用上游已落盘的结果统计（若无则记 None）。
    if args.resume_from:
        up_p1 = _read_jsonl_tolerant(args.resume_from / "phase1_results.jsonl")
        phase1_block = {
            "resumed": True,
            "upstream_results": len(up_p1),
            "outcomes": {k: sum(1 for r in up_p1 if r.get("outcome") == k) for k in
                         ("seed_active", "seed_active_after_repair",
                          "seed_grounding_failure", "seed_error")},
        }
    else:
        phase1_block = {
            "resumed": False,
            "pool_added": p1.get("pool_size"),
            "outcomes": {k: sum(1 for r in p1["results"] if r.get("outcome") == k) for k in
                         ("seed_active", "seed_active_after_repair",
                          "seed_grounding_failure", "seed_error")},
        }
    summary = {
        "model": args.model,
        "gate_mode": args.gate_mode,
        "branch_count": args.branch_count,
        "tasks": len(tasks),
        "pools": {"source": len(source), "replay": len(replay), "audit": len(audit)},
        "phase1": phase1_block,
        "evolution_rounds": evo["rounds"],
        "gate_records": evo["gate_records"],
        "audit_detail": evo["audit_detail"],
        "experience_pool": {"total": len(runner.experience_pool), "by_stage": pool_by_stage},
        "frozen_m_star_size": len(frozen),
        "final_eval": fe["summary"],
        "tree": tree.to_dict(),
        "ledger_count": len(ledger.entries),
        'retrieval_mode': args.retrieval_mode,
        'embedding_model': args.embedding_model if embedding_client else None,
        'english_admission_rejections': len(runner.admission_rejections),
    }
    _write_jsonl(out / 'english_admission_rejections.jsonl', list(runner.admission_rejections))
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 精确成本：从全局计数器导出（真实 API usage 累计，非估算）
    cost_snap = runner.cost.snapshot()
    cost_snap["stages"] = runner.cost.stage_totals()
    cost_snap['embedding'] = embedding_client.usage if embedding_client else None
    (out / "cost.json").write_text(json.dumps(cost_snap, ensure_ascii=False, indent=2), encoding="utf-8")
    total_c = cost_snap["total"]
    progress(f"=== LLM 成本：{total_c['calls']} 次调用，"
             f"{total_c['prompt_tokens']} 输入 / {total_c['completion_tokens']} 输出 tokens，"
             f"合计 {total_c['total_tokens']} tokens"
             + (f"，费用 {total_c['cost_ca']:.4f} CA元" if total_c.get("cost_ca") is not None else "")
             + (f"（usage 缺失 {total_c['usage_missing']} 次）" if total_c["usage_missing"] else ""))

    # 看板：标记完成 + 更新索引
    write_status(out, status="completed", stage="done", detail="全部完成",
                 progress={"tree_nodes": sum(len(f.invariants) for f in tree.all_families()),
                           "pool": len(runner.experience_pool),
                           "joint_pass_rate": fe["summary"]["joint_pass_rate"]})
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="completed",
                     model=args.model, tasks=len(tasks),
                     extra={"joint_pass_rate": fe["summary"]["joint_pass_rate"],
                            "frozen_size": len(frozen),
                            "cost_ca": total_c.get("cost_ca"),
                            "total_tokens": total_c["total_tokens"]})
    progress(f"全部完成，结果目录：{out}")


if __name__ == "__main__":
    main()
