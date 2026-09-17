"""M* 冻结与冻结后 Base/Plus 评测（阶段 H，DOCX Phase 4��。

所属阶段：CLE 第四阶段——经验树迭代收敛后锁定经验库，在 CodeSecEval-X 上隔离评测。
输入：CLE 运行产出的 tree.json（HSK-Tree）、Base/Plus 数据集、LLM 请求器。
输出：frozen/m_star.jsonl + freeze_metadata.json；validation_runs/<subset>/rows.jsonl
  与 summary.json；含 Function/Secure/Joint 与四态分布的报告。

验证证据：Base/Plus 任务用 Docker 官方 Python 验证器（Test-FP/Test-SP 双套件）执行，
  编译失败/超时/未达标一律记 0 且不缩分母。

硬性红线（AGENTS.md）：冻结后 feedback_channel=disabled，评测结果严禁回流经验库。
  本模块只读冻结树，任何写记忆的入口在冻结态下抛 freeze_violation。

四态与主指标映射：A=Joint、B=Function-only、C=Secure-only、D=neither；
  主指标为 Function/Secure/Joint（A 态占比）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata

from .hsk_tree import HskTree, SecurityInvariantNode


def freeze_tree(tree: HskTree, out_dir: Path, *, model: str = "deepseek-v3.2") -> dict[str, Any]:
    """把 HSK-Tree 冻结为 m_star.jsonl，并写出带 SHA-256 的 freeze_metadata.json。

    哈希对 **m_star.jsonl 文件字节** 计算，与 finalize_plt_evaluation 的校验口径一致。
    只导出 active 节点（retired/consolidated 不参与检索）。
    """
    frozen_dir = out_dir / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    m_star_path = frozen_dir / "m_star.jsonl"

    # to_jsonl() 已返回序列化后的 dict（每行一个 active/其他节点，附带 cwe 路由）
    rows = [r for r in tree.to_jsonl() if r.get("status") == "active"]
    m_star_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    digest = hashlib.sha256(m_star_path.read_bytes()).hexdigest()
    metadata = build_freeze_metadata(rows, model, "hsk-tree-retriever-v1", "llm-bounded-v1")
    metadata["memory_sha256"] = digest  # 以文件字节哈希为准
    metadata["m_star_path"] = str(m_star_path)
    metadata["active_nodes"] = len(rows)
    (frozen_dir / "freeze_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def load_frozen_tree(m_star_path: Path) -> HskTree:
    """从 m_star.jsonl 重建只读 HSK-Tree（供检索，不写回）。"""
    tree = HskTree()
    for line in m_star_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        node = SecurityInvariantNode.from_dict(json.loads(line))
        node.status = "active"
        tree.insert_node(node)
    return tree
