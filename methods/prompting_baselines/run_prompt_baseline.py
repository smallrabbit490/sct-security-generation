"""Small explicit runner for the four direct prompt baselines."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from prompts import PROMPTS, build_prompt


def load_rows(dataset_root: Path, subset: str, language: str) -> list[dict]:
    names = {"python": "Python", "cpp": "Cpp", "go": "Go", "java": "Java", "js": "JS"}
    path = dataset_root / subset / f"{names[language]}_{subset}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--dataset-root", type=Path, default=Path("data/SecEvoBasePlus"))
    parser.add_argument("--subset", default="Base")
    parser.add_argument("--language", default="python")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--model", default="glm-5.1")
    args = parser.parse_args()
    if args.check_only:
        print("direct prompt methods:", ", ".join(PROMPTS))
        return
    rows = load_rows(args.dataset_root, args.subset, args.language)
    for row in rows[: args.limit]:
        for method in PROMPTS:
            prompt = build_prompt(method, args.language, row.get("Problem", ""), row.get("Entry_Point", ""))
            print(json.dumps({"task_id": row.get("ID"), "method": method, "model": args.model, "prompt": prompt}, ensure_ascii=False))


if __name__ == "__main__":
    main()
