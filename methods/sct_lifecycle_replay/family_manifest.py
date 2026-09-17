"""读取新版 PLT family 元数据，不改变原始数据内容。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_family_manifest(path: str | Path) -> dict[str, Any]:
    """读取并校验 family manifest；row 分类是后续分配器唯一输入。"""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest.get("row_classification"), dict):
        raise ValueError("family manifest 缺少 row_classification")
    for row_id, item in manifest["row_classification"].items():
        if not item.get("seed_family_id") or not item.get("cwe_family"):
            raise ValueError(f"row {row_id} 缺少 family 或 CWE")
    return manifest


def family_id_for_row(manifest: dict[str, Any], row_id: int) -> str:
    """返回任务所属 family；family 来源必须可追溯。"""
    item = manifest["row_classification"].get(str(row_id))
    if item is None:
        raise KeyError(f"row {row_id} 不在 family manifest")
    return str(item["seed_family_id"])
