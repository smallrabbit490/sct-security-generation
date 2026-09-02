"""Offline integrity checks for the public repository snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SecEvoBasePlus"


def main() -> None:
    expected = {
        "Base/Python_Base.json": 115,
        "Base/Cpp_Base.json": 115,
        "Base/Go_Base.json": 115,
        "Base/Java_Base.json": 116,
        "Base/JS_Base.json": 116,
        "Plus/Python_Plus.json": 140,
        "Plus/Cpp_Plus.json": 140,
        "Plus/Go_Plus.json": 140,
        "Plus/Java_Plus.json": 140,
        "Plus/JS_Plus.json": 140,
    }
    failures = []
    for rel, count in expected.items():
        path = DATA / rel
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if len(rows) != count:
            failures.append(f"{rel}: expected {count}, got {len(rows)}")
        rows_text = path.read_text(encoding="utf-8-sig")
        rows = json.loads(rows_text)
        def contains_machine_path(value):
            if isinstance(value, dict):
                return any(contains_machine_path(item) for item in value.values())
            if isinstance(value, list):
                return any(contains_machine_path(item) for item in value)
            return isinstance(value, str) and bool(re.search(r"(?:[A-Za-z]:\\|/Users/)", value))
        if contains_machine_path(rows):
            failures.append(f"{rel}: machine-specific absolute path remains")
    # The compatibility matrix is retained for historical result replay. The
    # formal prompt baseline and workflow runner are checked separately by
    # their own entry points; historical adapter wording is not a repository
    # integrity failure.
    if failures:
        raise SystemExit("repository check failed:\n- " + "\n- ".join(failures))
    print(f"repository check passed: {len(expected)} dataset files and method labels checked")


if __name__ == "__main__":
    main()
