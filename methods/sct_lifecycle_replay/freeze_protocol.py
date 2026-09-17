"""冻结 M*、检索器和调度策略，阻断 Base/Plus 反馈回流。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_freeze_metadata(memory: list[dict], model: str, retriever: str, scheduler: str) -> dict[str, Any]:
    """生成可审计冻结清单；只记录摘要，不记录 API key。"""
    encoded = json.dumps(memory, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "frozen": True,
        "model": model,
        "retriever": retriever,
        "scheduler": scheduler,
        "memory_sha256": hashlib.sha256(encoded).hexdigest(),
        "feedback_channel": "disabled",
    }
