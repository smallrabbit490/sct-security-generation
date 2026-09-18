"""LLM 调用成本精确计数器（线程安全）。

所属阶段：全流程（Phase1/2/3 与最终评测）——每个 LLM 调用点上报 usage。
职责：把 ChatAnywhere 响应里的 `usage` 字段按**调用点标签**累计，算出精确的
    次数、输入/输出 token 与费用（CA元）。看板据此显示真实成本，不再用粗估。
输入：requester 每次返回的响应体（取 response["usage"]）。
输出：record() 累计；snapshot() 导出可分阶段/分调用点的明细；落盘 cost.json。
验证证据：本模块统计的是**真实 API 返回的计费 token**，不是本地估算；
    若响应缺 usage，会记入 `usage_missing` 而**不默认为 0**（避免看起来便宜）。
失败类型：网络异常由上层处理；本模块只处理"有响应但缺 usage"的情况。
允许修改长期经验库：否——纯统计。
"""

from __future__ import annotations

import threading
from typing import Any

# 单价表（CA元 / 1K tokens）。来源：ChatAnywhere 官方《费用标准及模型列表》
# https://chatanywhere.apifox.cn/doc-2694962 （查询日期 2026-09-18）
# 注意：官方页面注明"价格随着供应商的变动而变动"，如需精确对账请重新核对。
PRICING: dict[str, dict[str, float]] = {
    "deepseek-v3.2": {"input": 0.0012, "output": 0.0018},
    "deepseek-chat": {"input": 0.0012, "output": 0.0018},
    "deepseek-v4-flash": {"input": 0.0012, "output": 0.0036},
    "deepseek-v4.1-flash": {"input": 0.0009, "output": 0.0036},
    "deepseek-v4-pro": {"input": 0.0045, "output": 0.0135},
    "deepseek-reasoner": {"input": 0.0024, "output": 0.0096},
}
PRICING_SOURCE = "ChatAnywhere 费用标准 https://chatanywhere.apifox.cn/doc-2694962 (2026-09-18)"


class CostTracker:
    """线程安全的 LLM 成本计数器。

    用法：
        tracker = CostTracker(model="deepseek-v3.2")
        tracker.record("phase1.gen", response)          # 直接喂响应体
        tracker.record("phase2.distill", response)
        print(tracker.snapshot())
    """

    def __init__(self, model: str = "deepseek-v3.2") -> None:
        self.model = model
        self._lock = threading.Lock()
        # label -> {calls, prompt_tokens, completion_tokens, cached_tokens, usage_missing}
        self._buckets: dict[str, dict[str, int]] = {}
        # 阶段上下文：由编排器在进入各阶段时设置，用于把共享调用点归到正确阶段。
        # 例如 gen.pipeline 在 Phase1 与 Phase2 都会调用，但应分别计费。
        self._stage_ctx = threading.local()

    # ---- 阶段上下文（线程局部，避免并发任务互相污染） ----
    def set_stage(self, stage: str) -> None:
        """设置当前线程的阶段标签（phase1/phase2/phase3/final_eval）。

        注意：threading.local 不跨线程继承，因此在**并发 worker 内部**也要设置一次，
        否则工作线程里发出的调用会被记到 other。编排器在 _map 的任务函数开头调用。
        """
        self._stage_ctx.stage = stage

    def stage_scope(self, stage: str):
        """上下文管理器：在 with 块内把当前阶段设为 stage（含 worker 线程内使用）。"""
        tracker = self

        class _Scope:
            def __enter__(self_inner):
                self_inner.prev = tracker.current_stage()
                tracker.set_stage(stage)
                return tracker

            def __exit__(self_inner, *exc):
                tracker.set_stage(self_inner.prev)
                return False

        return _Scope()

    def current_stage(self) -> str:
        return getattr(self._stage_ctx, "stage", "other")

    def _bucket(self, label: str) -> dict[str, int]:
        if label not in self._buckets:
            self._buckets[label] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                    "cached_tokens": 0, "usage_missing": 0, "errors": 0}
        return self._buckets[label]

    def record(self, label: str, response: Any) -> None:
        """记录一次成功调用的 usage。response 缺 usage 时计入 usage_missing。

        实际桶名 = "<阶段>.<调用点>"，阶段由 set_stage 设置（并发下按线程隔离）。
        """
        usage = None
        if isinstance(response, dict):
            usage = response.get("usage")
        key = f"{self.current_stage()}.{label}"
        with self._lock:
            b = self._bucket(key)
            b["calls"] += 1
            if not isinstance(usage, dict):
                b["usage_missing"] += 1
                return
            b["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            b["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            details = usage.get("prompt_tokens_details") or {}
            b["cached_tokens"] += int(details.get("cached_tokens") or 0)

    def record_error(self, label: str) -> None:
        """记录一次失败调用（无 usage），单独计数以便区分'便宜'和'没测到'。"""
        key = f"{self.current_stage()}.{label}"
        with self._lock:
            b = self._bucket(key)
            b["calls"] += 1
            b["errors"] += 1

    def _cost_of(self, prompt_tokens: int, completion_tokens: int) -> float | None:
        price = PRICING.get(self.model)
        if not price:
            return None
        return round(prompt_tokens / 1000 * price["input"] + completion_tokens / 1000 * price["output"], 6)

    def snapshot(self) -> dict[str, Any]:
        """导出明细：分调用点 + 汇总。费用为 None 表示该模型无单价（只报 token）。"""
        with self._lock:
            buckets = {k: dict(v) for k, v in self._buckets.items()}
        by_label: dict[str, dict] = {}
        tot = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
               "cached_tokens": 0, "usage_missing": 0, "errors": 0}
        for label, b in sorted(buckets.items()):
            cost = self._cost_of(b["prompt_tokens"], b["completion_tokens"])
            by_label[label] = {**b, "total_tokens": b["prompt_tokens"] + b["completion_tokens"],
                               "cost_ca": cost}
            for k in tot:
                tot[k] += b[k]
        total_cost = self._cost_of(tot["prompt_tokens"], tot["completion_tokens"])
        return {
            "model": self.model,
            "pricing": PRICING.get(self.model),
            "pricing_source": PRICING_SOURCE,
            "currency": "CA元",
            "by_label": by_label,
            "total": {**tot, "total_tokens": tot["prompt_tokens"] + tot["completion_tokens"],
                      "cost_ca": total_cost},
            "note": ("usage 缺失的调用计入 usage_missing，未按 0 计费；"
                     "errors 为调用失败的次数（无 usage）"),
        }

    def stage_totals(self) -> dict[str, dict]:
        """按桶名的阶段前缀（phase1/phase2/phase3/final_eval/other）汇总，供看板分阶段展示。"""
        snap = self.snapshot()
        stages: dict[str, dict] = {}
        for label, b in snap["by_label"].items():
            stage = label.split(".")[0] if "." in label else "other"
            s = stages.setdefault(stage, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                          "total_tokens": 0, "cost_ca": 0.0,
                                          "cached_tokens": 0, "usage_missing": 0, "errors": 0})
            s["calls"] += b["calls"]
            s["prompt_tokens"] += b["prompt_tokens"]
            s["completion_tokens"] += b["completion_tokens"]
            s["total_tokens"] += b["total_tokens"]
            s["cached_tokens"] += b["cached_tokens"]
            s["usage_missing"] += b["usage_missing"]
            s["errors"] += b["errors"]
            if b["cost_ca"] is not None and s["cost_ca"] is not None:
                s["cost_ca"] = round(s["cost_ca"] + b["cost_ca"], 6)
            else:
                s["cost_ca"] = None
        return stages


# 全局单例：闭包式入口（provider/agent 侧只需 requester 包装即可上报）
_GLOBAL: CostTracker | None = None
_GLOBAL_LOCK = threading.Lock()


def global_tracker(model: str | None = None) -> CostTracker:
    """取全局计数器（首次调用时按 model 初始化）。"""
    global _GLOBAL
    with _GLOBAL_LOCK:
        if _GLOBAL is None:
            _GLOBAL = CostTracker(model or "deepseek-v3.2")
        elif model:
            _GLOBAL.model = model
        return _GLOBAL


def reset_global() -> None:
    """重置全局计数器（测试用）。"""
    global _GLOBAL
    with _GLOBAL_LOCK:
        _GLOBAL = None


def labeled(requester, label: str, tracker: CostTracker | None = None):
    """把一个 requester 包装成"带调用点标签"的版本，自动上报 usage。

    这样各模块（agent_pipeline / retriever / distillation / active_replay /
    source_knowledge / consolidate）无需改动内部实现，只要在构造时传入
    `labeled(base_requester, "phase1.gen")` 即可精确归集成本。

    失败调用（异常）会记入 errors 后原样抛出，不吞异常。
    """
    tr = tracker or global_tracker()

    def wrapped(prompt: str, *args, **kwargs):
        try:
            resp = requester(prompt, *args, **kwargs)
        except Exception:
            tr.record_error(label)
            raise
        tr.record(label, resp)
        return resp

    return wrapped
