from dataclasses import dataclass, field
from typing import Any


def truncate_text(value: object, limit: int = 2000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    omitted = len(text) - len(head) - len(tail)
    return f"{head}\n...[truncated {omitted} chars]...\n{tail}"


@dataclass
class TranslationResult:
    code: str
    language: str
    source_field: str
    model: str
    attempts: int = 1
    error: str | None = None


@dataclass
class ValidationResult:
    ok: bool
    language: str
    mode: str
    stdout: str = ""
    stderr: str = ""
    details: dict[str, Any] = field(default_factory=dict)
