"""Remove machine-specific paths from the copied dataset without changing code."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SecEvoBasePlus"
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
        value = re.sub(r"sk-[A-Za-z0-9]{20,}", "<REDACTED_API_KEY>", value)
        return value
    return value


def main() -> None:
    for path in sorted(DATA.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
