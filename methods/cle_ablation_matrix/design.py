"""细粒度 CLE 消融矩阵。

每个变体都必须独立从自己的上游状态重跑并冻结；components 只描述唯一变化，
便于相邻比较归因。该模块不执行模型调用，也不读最终测试反馈。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ArmSpec:
    arm_id: str
    stage: str
    parent_arm: str | None
    train_pools: tuple[str, ...]
    components: Mapping[str, Any]
    freeze_policy: str
    purpose: str
    evaluation_sets: tuple[str, ...] = ("Base", "Plus", "H_pass")


def _arm(arm_id, stage, parent, pools, components, freeze, purpose):
    return ArmSpec(arm_id, stage, parent, tuple(pools), dict(components), freeze, purpose)


ARM_SPECS: dict[str, ArmSpec] = {
    "C1-0": _arm("C1-0", "c1", None, (), {"memory": False}, "none", "无经验库最终评测基线"),
    "C1-1": _arm("C1-1", "c1", None, ("D_init",), {"analysis": False, "planning": False, "codegen": True, "extract": True, "repair": False, "inject_prev_evidence": False}, "C3-0", "直接 CodeGen 后提取经验"),
    "C1-2": _arm("C1-2", "c1", "C1-1", ("D_init",), {"analysis": True, "planning": True, "codegen": True, "extract": True, "repair": False, "inject_prev_evidence": False}, "C3-0", "Analysis/Planning 对冷启动经验质量的贡献"),
    "C1-3": _arm("C1-3", "c1", "C1-2", ("D_init",), {"analysis": True, "planning": True, "codegen": True, "extract": True, "repair": True, "inject_prev_evidence": True}, "C3-0", "修复和上一轮失败证据注入的贡献"),
    "C2-0": _arm("C2-0", "c2", "C1-3", ("D_init", "D_grow"), {"replay": False, "retrieval": False, "retrieval_mode": "flat_rule", "distillation": False, "reanalyze_after_retrieval": False, "repairs": 0, "failure_evidence": False, "hsk_tree": False}, "C3-0", "无回放/进化对照"),
    "C2-1": _arm("C2-1", "c2", "C2-0", ("D_init", "D_grow"), {"replay": True, "retrieval": False, "retrieval_mode": "flat_rule", "distillation": False, "reanalyze_after_retrieval": False, "repairs": 0, "failure_evidence": False, "hsk_tree": False}, "C3-0", "Replay 与轨迹提炼（规则检索关闭 LLM 打分）"),
    "C2-2": _arm("C2-2", "c2", "C2-1", ("D_init", "D_grow"), {"replay": True, "retrieval": True, "retrieval_mode": "flat_llm", "distillation": True, "reanalyze_after_retrieval": False, "repairs": 0, "failure_evidence": False, "hsk_tree": False}, "C3-0", "检索和蒸馏"),
    "C2-3": _arm("C2-3", "c2", "C2-2", ("D_init", "D_grow"), {"replay": True, "retrieval": True, "retrieval_mode": "flat_llm", "distillation": True, "reanalyze_after_retrieval": True, "repairs": 0, "failure_evidence": False, "hsk_tree": False}, "C3-0", "检索后再分析"),
    "C2-4": _arm("C2-4", "c2", "C2-3", ("D_init", "D_grow"), {"replay": True, "retrieval": True, "retrieval_mode": "flat_llm", "distillation": True, "reanalyze_after_retrieval": True, "repairs": 1, "failure_evidence": True, "hsk_tree": False}, "C3-0", "修复、失败证据和错题本"),
    "C2-5": _arm("C2-5", "c2", "C2-4", ("D_init", "D_grow"), {"replay": True, "retrieval": True, "retrieval_mode": "flat_llm", "distillation": True, "reanalyze_after_retrieval": True, "repairs": 1, "failure_evidence": True, "hsk_tree": True}, "C3-0", "HSK-Tree 吸收归并剪枝"),
    "C2-B1": _arm("C2-B1", "support", "C2-5", ("D_init", "D_grow"), {"branch_count": 1}, "C3-0", "多 Agent 单分支"),
    # 三分支生成依赖上下文流水线；该依赖必须显式写入臂配置，避免命令行校验在启动后才失败。
    "C2-B3": _arm("C2-B3", "support", "C2-5", ("D_init", "D_grow"), {"branch_count": 3, "context_pipeline": True}, "C3-0", "多 Agent 三分支"),
    "C2-R0": _arm("C2-R0", "support", "C2-5", ("D_init", "D_grow"), {"repairs": 0}, "C3-0", "无修复预算辅助臂"),
    "C2-R1": _arm("C2-R1", "support", "C2-5", ("D_init", "D_grow"), {"repairs": 1}, "C3-0", "单修复预算辅助臂"),
    "C2-E0": _arm("C2-E0", "support", "C2-5", ("D_init", "D_grow"), {"inject_prev_evidence": False}, "C3-0", "不注入上一轮证据辅助臂"),
    "C2-E1": _arm("C2-E1", "support", "C2-5", ("D_init", "D_grow"), {"inject_prev_evidence": True}, "C3-0", "注入上一轮证据辅助臂"),
    "C2-I0": _arm("C2-I0", "support", "C2-5", ("D_init", "D_grow"), {"internal_checks": False}, "C3-0", "无内部检查辅助臂"),
    # 内部检查要求同时打开上下文流水线和上一轮证据注入，否则 runner 会拒绝启动。
    "C2-I1": _arm("C2-I1", "support", "C2-5", ("D_init", "D_grow"), {"internal_checks": True, "context_pipeline": True, "inject_prev_evidence": True}, "C3-0", "有内部检查辅助臂"),
    "C2-A0": _arm("C2-A0", "support", "C2-5", ("D_init", "D_grow"), {"anti_overdefense": "base"}, "C3-0", "基础过度防御策略"),
    "C2-A1": _arm("C2-A1", "support", "C2-5", ("D_init", "D_grow"), {"anti_overdefense": "anti_od"}, "C3-0", "反过度防御策略"),
    "C2-A2": _arm("C2-A2", "support", "C2-5", ("D_init", "D_grow"), {"anti_overdefense": "contract_freeze"}, "C3-0", "契约冻结策略"),
    "C2-T0": _arm("C2-T0", "support", "C2-5", ("D_init", "D_grow"), {"retrieval_mode": "flat_rule"}, "C3-0", "规则检索辅助臂"),
    "C2-T1": _arm("C2-T1", "support", "C2-5", ("D_init", "D_grow"), {"retrieval_mode": "flat_llm"}, "C3-0", "平面 LLM 检索辅助臂"),
    "C2-T2": _arm("C2-T2", "support", "C2-5", ("D_init", "D_grow"), {"retrieval_mode": "semantic_llm"}, "C3-0", "语义 LLM 检索辅助臂"),
    "C3-0": _arm("C3-0", "c3", "C2-5", ("D_init", "D_grow", "D_gate"), {"format_source_checks": True, "quality_gate": False, "independent_validity": False, "h_pass_regression": False}, "C3-0", "格式与来源校验冻结"),
    "C3-1": _arm("C3-1", "c3", "C3-0", ("D_init", "D_grow", "D_gate"), {"format_source_checks": True, "quality_gate": True, "independent_validity": False, "h_pass_regression": False}, "C3-1", "质量门控"),
    "C3-2": _arm("C3-2", "c3", "C3-1", ("D_init", "D_grow", "D_gate"), {"format_source_checks": True, "quality_gate": True, "independent_validity": True, "h_pass_regression": False}, "C3-2", "独立动态有效性门控"),
    "C3-3": _arm("C3-3", "c3", "C3-2", ("D_init", "D_grow", "D_gate"), {"format_source_checks": True, "quality_gate": True, "independent_validity": True, "h_pass_regression": True}, "C3-3", "H_pass 回归门控"),
}


def get_arm(arm_id: str) -> ArmSpec:
    try:
        return ARM_SPECS[arm_id]
    except KeyError as exc:
        raise ValueError(f"unknown CLE ablation arm: {arm_id}") from exc


def validate_design() -> None:
    for arm_id, spec in ARM_SPECS.items():
        if arm_id != spec.arm_id or spec.stage not in {"c1", "c2", "c3", "support"}:
            raise ValueError(f"invalid arm metadata: {arm_id}")
        if spec.parent_arm and spec.parent_arm not in ARM_SPECS:
            raise ValueError(f"missing parent arm: {arm_id}")
        if spec.parent_arm == arm_id:
            raise ValueError(f"cyclic parent arm: {arm_id}")
        if "H_pass" in spec.train_pools:
            raise ValueError(f"H_pass cannot train arm: {arm_id}")
    for arm_id in ARM_SPECS:
        seen = set()
        current = arm_id
        while current:
            if current in seen:
                raise ValueError(f"parent cycle: {arm_id}")
            seen.add(current)
            current = ARM_SPECS[current].parent_arm
