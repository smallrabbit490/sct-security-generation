"""生成精简运行报告，避免保存原始提示、密钥或长响应。

所属阶段：运行收尾的报告与元数据写入（文档 11.1 的运行目录约定）。
输入：summary 指标 dict 与运行 metadata（模型、语言适配、反馈通道）。
输出：summary.json、run_metadata.json、lifecycle_replay_report.md。
摘要只含聚合指标与计数，不含 API key、原始 prompt、隐藏测试或长响应。
"""

from __future__ import annotations

import json
from pathlib import Path


def write_report(out: Path, summary: dict, metadata: dict) -> None:
    """写入人工可读报告和机器可读运行元数据。"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 生命周期回放运行报告",
        "",
        f"- 来源任务：{summary.get('source_tasks', 0)}",
        f"- 种子经验：joint {summary.get('seed_joint', 0)} / partial {summary.get('seed_partial', 0)} / 失败入错题本 {summary.get('seed_failed_to_error_ledger', 0)}",
        f"- 回放任务：{summary.get('replay_tasks', 0)}",
        f"- 审查任务：{summary.get('audit_tasks', 0)}",
        f"- 候选经验：{summary.get('candidates', 0)}",
        f"- 晋升经验：{summary.get('promoted', 0)}",
        f"- 降级经验：{summary.get('demoted', 0)}",
        f"- 修订经验：{summary.get('revised', 0)}",
        f"- 冻结经验：{summary.get('frozen_memory', 0)}",
        f"- 主动回放：{'启用' if summary.get('active_replay') else '未启用'}（决策记录 {summary.get('replay_decisions', 0)} 条）",
        f"- 回放联合通过：{summary.get('trajectory_joint_pass', 0)}/{summary.get('replay_tasks', 0)}",
        "",
        "所有 Base/Plus 反馈通道在冻结后关闭。",
    ]
    (out / "lifecycle_replay_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
