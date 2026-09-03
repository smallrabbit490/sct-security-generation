"""Remove machine-specific paths from the copied dataset without changing code."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SecEvoBasePlus"
EXTERNAL = ROOT / "data" / "external"
LOCAL_ROOT = re.escape(r"D:\thecourceofdasi\safecodernew")


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, str):
        # Only replace the known source-machine prefix and Windows absolute
        # paths.  Do not rewrite POSIX paths such as /tmp used by test code.
        value = re.sub(LOCAL_ROOT + r"(?:\\[^\"\r\n]*)?", "<LOCAL_PATH>", value, flags=re.IGNORECASE)
        value = re.sub(r"[A-Za-z]:\\(?:[^\"\r\n]*\\?)*[^\"\r\n]*", "<LOCAL_PATH>", value)
        value = re.sub(r"[A-Za-z]:/(?:[^\"\r\n]*/)*[^\"\r\n]*", "<LOCAL_PATH>", value)
        value = re.sub(r"sk-[A-Za-z0-9]{20,}", "<REDACTED_API_KEY>", value)
        value = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "<REDACTED_API_KEY>", value)
        value = re.sub(r"(?i)(api[_-]?key|api[_-]?secret|client[_-]?secret)\s*([:=])\s*(['\"])[^'\"]+\3", r"\1\2\3<REDACTED_SECRET>\3", value)
        return value
    return value


def main() -> None:
    for path in sorted(list(DATA.rglob("*")) + list(EXTERNAL.rglob("*"))):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".csv", ".py", ".txt", ".md"}:
            continue
        if path.suffix.lower() == ".jsonl":
            lines = [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            path.write_text("\n".join(json.dumps(clean(json.loads(line)), ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(clean(path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
