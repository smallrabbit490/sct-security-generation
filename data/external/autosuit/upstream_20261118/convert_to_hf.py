"""
Convert AutoSUIT Bench raw CSVs into HuggingFace-ready JSONL, one file per language.

Each output row is a SELF-CONTAINED evaluation sample: it carries the task
instruction (`code_description`), optional context (`cwe_description`,
`vulnerable_code`, `completion_prefix`), the reference solutions, and BOTH unit
test suites inline, plus the exact filename the generated code must be written to
so the tests can import/`#include` it.

Run from inside AutoSUIT_HF_AMAZON/ (reads raw/, writes <lang>/test.jsonl):

    python convert_to_hf.py

The script is path-independent: it resolves the author's absolute `root_path`
column down to the matching folder under raw/.
"""

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
RAW = REPO / "raw"

# CSV root_path (author's machine) -> folder under raw/. Matched by trailing segment.
ROOT_SEGMENT_MAP = {
    "python": RAW / "python",
    "java": RAW / "java",
    "c": RAW / "c",
    "c_v2": RAW / "c",          # a few C rows were regenerated under c_v2
    "cpp": RAW / "cpp",
    "ref_code": RAW / "ref_code",
}

LANG_CONFIG = {
    "python": {"csv": "dataset_py.csv", "ext": ".py"},
    "java":   {"csv": "dataset_java.csv", "ext": ".java"},
    "c":      {"csv": "dataset_c.csv", "ext": ".c"},
    "cpp":    {"csv": "dataset_cpp.csv", "ext": ".cpp"},
}

# Role suffixes on code files. Order matters: longest/translate first.
ROLE_SUFFIXES = [
    "_unsecure_translate", "_secure_translate", "_upgrade_translate",
    "_unsecure", "_secure", "_upgrade",
]

CODE_FENCE = {"python": "python", "java": "java", "c": "c", "cpp": "cpp"}


def read_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def resolve_dir(root_path: str) -> Path | None:
    seg = root_path.rstrip("/").split("/")[-1]
    return ROOT_SEGMENT_MAP.get(seg)


def module_base(file_name: str, ext: str) -> str:
    """The identifier the test imports / #includes, WITHOUT extension.

    Examples:
      cwe_119_3_unsecure.c            -> cwe_119_3         (test: #include "cwe_119_3.c")
      cwe_119_3_unsecure_translate.cpp-> cwe_119_3         (test: #include "cwe_119_3.cpp")
      cwe_022_2_mask_0.py             -> cwe_022_2_task    (test: from cwe_022_2_task import ...)
      cwe_117_0_task.py               -> cwe_117_0_task
    """
    name = file_name[: -len(ext)] if file_name.endswith(ext) else file_name
    for suf in ROLE_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    # ref_code convention: masks and task both import from the *_task module
    if "_mask_" in name:
        return name.rsplit("_mask_", 1)[0] + "_task"
    return name  # e.g. cwe_117_0_task


def code_extension(lang: str, file_name: str, ext: str) -> str:
    """The filename generated code must be written to so tests resolve it."""
    base = module_base(file_name, ext)
    return f"{base}{ext}"


def completion_prefix(secure_code: str, fraction: float = 0.30) -> str:
    """First `fraction` of the secure code by lines, as the code-completion prefix (Task 4)."""
    if not secure_code:
        return ""
    lines = secure_code.splitlines(keepends=True)
    n = max(1, int(len(lines) * fraction))
    return "".join(lines[:n])


def clean_cwe_desc(raw: str) -> str:
    """cwe_description is stored as a Python repr'd 1-tuple: ("text",). Unwrap it."""
    if not raw:
        return ""
    raw = raw.strip()
    try:
        import ast
        val = ast.literal_eval(raw)
        if isinstance(val, (tuple, list)) and val:
            return str(val[0])
        return str(val)
    except Exception:
        return raw


def find_sibling(directory: Path, base: str, role: str, ext: str) -> Path | None:
    """Find e.g. the *_secure* file for a module base (handles the _translate suffix)."""
    for cand in sorted(directory.glob(f"{base}{role}*{ext}")):
        return cand
    return None


def process_language(lang: str, cfg: dict) -> list[dict]:
    ext = cfg["ext"]
    rows = list(csv.DictReader(open(RAW / cfg["csv"], encoding="utf-8")))
    samples, missing = [], 0

    for idx, row in enumerate(rows):
        directory = resolve_dir(row["root_path"].strip())
        if directory is None:
            print(f"  [{lang}] WARN unresolved root_path: {row['root_path']}")
            continue

        file_name = row["file_name"].strip()
        source_code = read_file(directory / file_name)
        if source_code is None:
            missing += 1
            continue

        base = module_base(file_name, ext)
        code_file = f"{base}{ext}"  # write generated code here for the tests to find it

        # Reference solutions (both vulnerable and secure when present in the folder)
        vuln_path = find_sibling(directory, base, "_unsecure", ext)
        sec_path = find_sibling(directory, base, "_secure", ext)
        # ref_code python: the *_task file is the reference secure-ish solution
        if sec_path is None and lang == "python" and base.endswith("_task"):
            sec_path = directory / f"{base}{ext}"
        vulnerable_code = read_file(vuln_path) if vuln_path else None
        secure_code = read_file(sec_path) if sec_path else None

        # Tests
        ft_name = row.get("funct_unit_test", "").strip()
        st_name = row.get("sec_unit_test", "").strip()
        functional_test = read_file(directory / ft_name) if ft_name else None
        security_test = read_file(directory / st_name) if st_name else None

        try:
            secure_status = int(row.get("secure_status", ""))
        except (ValueError, TypeError):
            secure_status = -1

        sample = {
            # ---- identity ----
            "id": f"{lang}_{idx}",
            "language": lang,
            "cwe_id": int(row["cwe_id"]),
            "reference_file_name": file_name,      # the file this CSV row indexes
            "secure_status": secure_status,        # 1 = reference file is secure, 0 = vulnerable
            # ---- how to run: write the model output to this filename in the sample dir ----
            "code_file_name": code_file,           # e.g. cwe_119_3.c / cwe_020_0_task.py
            "module_name": base,                   # importable/included name (no extension)
            # ---- task instruction & optional contexts ----
            "code_description": row.get("code_description", "") or "",
            "cwe_description": clean_cwe_desc(row.get("cwe_description", "")),
            "context": row.get("context", "") or "",           # extra usage context (python only)
            "vulnerable_code": vulnerable_code or "",           # Task 3 input (patching)
            "completion_prefix": completion_prefix(secure_code or ""),  # Task 4 input (30% prefix)
            # ---- reference solutions (for reference / not shown to model) ----
            "secure_code": secure_code or "",
            "sec_test_cases": row.get("sec_test_cases", "") or "",  # NL security scenarios
            # ---- evaluation harness: run these two suites ----
            "functional_test_file": ft_name,
            "functional_test": functional_test or "",
            "security_test_file": st_name,
            "security_test": security_test or "",
        }
        samples.append(sample)

    if missing:
        print(f"  [{lang}] WARN {missing} rows skipped (source file not found)")
    return samples


def main():
    total = 0
    for lang, cfg in LANG_CONFIG.items():
        samples = process_language(lang, cfg)
        out_dir = REPO / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "test.jsonl", "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        n_cwe = len({s["cwe_id"] for s in samples})
        print(f"{lang}: {len(samples)} samples, {n_cwe} CWEs -> {lang}/test.jsonl")
        total += len(samples)
    print(f"\nTotal: {total} samples")


if __name__ == "__main__":
    main()
