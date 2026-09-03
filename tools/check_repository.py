"""Offline integrity checks for the public repository snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SecEvoBasePlus"
EXTERNAL = ROOT / "data" / "external"


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
            return isinstance(value, str) and bool(re.search(r"(?:[A-Za-z]:[/\\]|/Users/)", value))
        if contains_machine_path(rows):
            failures.append(f"{rel}: machine-specific absolute path remains")
    external_json = {
        "secodeplt/secodeplt/data.json": 1411,
        "secodeplt/juliet/juliet_autocomplete.json": 263,
    }
    for rel, count in external_json.items():
        path = EXTERNAL / rel
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if len(rows) != count:
            failures.append(f"external/{rel}: expected {count}, got {len(rows)}")
        if contains_machine_path(rows):
            failures.append(f"external/{rel}: machine-specific absolute path remains")
    autosafe = EXTERNAL / "cweval" / "autosafecoder" / "dataset_copy.jsonl"
    if sum(bool(line.strip()) for line in autosafe.read_text(encoding="utf-8-sig").splitlines()) != 121:
        failures.append("external/cweval/autosafecoder/dataset_copy.jsonl: expected 121 records")
    external_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in EXTERNAL.rglob("*") if p.is_file())
    if re.search(r"(?:sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|[A-Za-z]:[/\\]Users[/\\])", external_text):
        failures.append("external: secret-like token or local user path remains")
    # The compatibility matrix is retained for historical result replay. The
    # formal prompt baseline and workflow runner are checked separately by
    # their own entry points; historical adapter wording is not a repository
    # integrity failure.
    if failures:
        raise SystemExit("repository check failed:\n- " + "\n- ".join(failures))
    print(f"repository check passed: {len(expected)} core files and external dataset checks")


if __name__ == "__main__":
    main()
