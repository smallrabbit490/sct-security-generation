from __future__ import annotations

import ast
import json
import math
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable


LANGUAGE_FILES = {
    "python": "Python_{subset}.json",
    "cpp": "Cpp_{subset}.json",
    "go": "Go_{subset}.json",
    "java": "Java_{subset}.json",
}

LANGUAGE_LABELS = {
    "python": "Python",
    "cpp": "C++",
    "go": "Go",
    "java": "Java",
}

GROWTH_BASELINE_MODES = {"none", "python_source", "same_language_reference"}

WarningProvider = Callable[[str, str, str | None], list[dict[str, str]]]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_records(dataset_root: Path, subsets: Iterable[str], languages: Iterable[str]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    records: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for subset in subsets:
        for language in languages:
            path = dataset_root / subset / LANGUAGE_FILES[language].format(subset=subset)
            records[(subset, language)] = read_json(path)
    return records


def _strip_comments_and_blanks(code: str) -> list[str]:
    lines = []
    in_block = False
    for raw in (code or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_block:
            if "*/" in line:
                in_block = False
                line = line.split("*/", 1)[1].strip()
            else:
                continue
        if line.startswith("/*"):
            in_block = "*/" not in line
            line = line.split("*/", 1)[-1].strip() if "*/" in line else ""
        if line.startswith("#") or line.startswith("//"):
            continue
        if line:
            lines.append(line)
    return lines


def logical_loc(code: str) -> int:
    return len(_strip_comments_and_blanks(code))


def _python_complexity(code: str) -> int:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return _regex_complexity(code)
    complexity = 1
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ExceptHandler,
        ast.IfExp,
        ast.Assert,
        ast.comprehension,
        ast.Match,
    )
    for node in ast.walk(tree):
        if isinstance(node, branch_nodes):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(1, len(node.values) - 1)
    return complexity


def _regex_complexity(code: str) -> int:
    text = code or ""
    patterns = [
        r"\bif\b",
        r"\belse\s+if\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bcase\b",
        r"\bcatch\b",
        r"\bexcept\b",
        r"\bswitch\b",
        r"\bselect\b",
        r"\?\s*[^:]+:",
        r"&&",
        r"\|\|",
    ]
    return 1 + sum(len(re.findall(pattern, text)) for pattern in patterns)


def cyclomatic_complexity(language: str, code: str) -> int:
    if language == "python":
        return _python_complexity(code)
    return _regex_complexity(code)


def static_warnings(language: str, code: str) -> list[dict[str, str]]:
    checks = {
        "python": [
            (r"\beval\s*\(", "high", "dynamic eval"),
            (r"\bexec\s*\(", "high", "dynamic exec"),
            (r"pickle\.loads?\s*\(", "high", "unsafe pickle deserialization"),
            (r"subprocess\.[^(]+\([^)]*shell\s*=\s*True", "high", "shell=True subprocess"),
            (r"yaml\.load\s*\(", "medium", "unsafe yaml.load"),
            (r"random\.", "low", "non-cryptographic randomness"),
            (r"except\s*:", "low", "bare except"),
        ],
        "cpp": [
            (r"\bgets\s*\(", "high", "unsafe gets"),
            (r"\bstrcpy\s*\(", "high", "unsafe strcpy"),
            (r"\bstrcat\s*\(", "high", "unsafe strcat"),
            (r"\bsprintf\s*\(", "medium", "unsafe sprintf"),
            (r"\bsystem\s*\(", "high", "system command execution"),
            (r"\bpopen\s*\(", "medium", "process execution"),
            (r"\brand\s*\(", "low", "non-cryptographic randomness"),
            (r"\bnew\s+", "low", "manual allocation"),
        ],
        "go": [
            (r"os/exec", "medium", "process execution package"),
            (r"\bexec\.Command\s*\(", "medium", "process execution"),
            (r"\bpanic\s*\(", "medium", "panic used for control flow"),
            (r"math/rand", "low", "non-cryptographic randomness"),
            (r"_\s*,\s*err\s*:=", "low", "discarded value with error path"),
            (r"if\s+err\s*!=\s*nil\s*\{\s*\}", "medium", "empty error handling"),
            (r"return\s+nil\s*,\s*nil", "low", "nil result and nil error"),
        ],
        "java": [
            (r"Runtime\.getRuntime\(\)\.exec\s*\(", "high", "runtime exec"),
            (r"new\s+ProcessBuilder\s*\(", "medium", "process builder"),
            (r"ObjectInputStream", "high", "java deserialization"),
            (r"XMLInputFactory\.newInstance\s*\(", "medium", "xml parser requires XXE hardening"),
            (r"DocumentBuilderFactory\.newInstance\s*\(", "medium", "xml parser requires XXE hardening"),
            (r"MessageDigest\.getInstance\s*\(\s*\"(?:MD5|SHA1|SHA-1)\"", "medium", "weak hash"),
            (r"new\s+Random\s*\(", "low", "non-cryptographic randomness"),
            (r"catch\s*\([^)]*\)\s*\{\s*\}", "medium", "empty catch block"),
        ],
    }
    warnings: list[dict[str, str]] = []
    for pattern, severity, message in checks.get(language, []):
        for match in re.finditer(pattern, code or "", flags=re.S):
            line = (code or "")[: match.start()].count("\n") + 1
            warnings.append({"severity": severity, "message": message, "line": str(line)})
    return warnings


def parse_bandit_warnings(payload: dict[str, Any]) -> list[dict[str, str]]:
    warnings = []
    for item in payload.get("results") or []:
        severity = str(item.get("issue_severity") or "LOW").lower()
        warnings.append({
            "tool": "bandit",
            "severity": severity,
            "message": str(item.get("issue_text") or ""),
            "line": str(item.get("line_number") or ""),
            "rule_id": str(item.get("test_id") or ""),
        })
    return warnings


def parse_govet_output(text: str) -> list[dict[str, str]]:
    warnings = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        warnings.append({
            "tool": "go_vet",
            "severity": "medium",
            "message": line.strip(),
            "line": "",
            "rule_id": "go_vet",
        })
    return warnings


def parse_gosec_warnings(payload: dict[str, Any]) -> list[dict[str, str]]:
    warnings = []
    for item in payload.get("Issues") or payload.get("issues") or []:
        severity = str(item.get("severity") or "LOW").lower()
        warnings.append({
            "tool": "gosec",
            "severity": severity,
            "message": str(item.get("details") or item.get("message") or ""),
            "line": str(item.get("line") or ""),
            "rule_id": str(item.get("rule_id") or item.get("rule") or ""),
        })
    return warnings


def parse_spotbugs_xml(text: str) -> list[dict[str, str]]:
    warnings = []
    for match in re.finditer(r'<BugInstance[^>]*type="([^"]+)"[^>]*priority="([^"]+)"', text or ""):
        priority = match.group(2)
        severity = "high" if priority == "1" else "medium" if priority == "2" else "low"
        warnings.append({
            "tool": "spotbugs",
            "severity": severity,
            "message": match.group(1),
            "line": "",
            "rule_id": match.group(1),
        })
    return warnings


def _run_command(args: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_bandit_analyzer(code: str, task_id: str | None = None, timeout: int = 60) -> list[dict[str, str]] | None:
    if not shutil.which("bandit"):
        return None
    with tempfile.TemporaryDirectory(prefix="safecoder_bandit_") as tmp:
        root = Path(tmp)
        source = root / "candidate.py"
        source.write_text(code or "", encoding="utf-8")
        proc = _run_command(["bandit", "-q", "-f", "json", str(source)], cwd=root, timeout=timeout)
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return None
        return parse_bandit_warnings(payload)


def run_go_vet_analyzer(code: str, task_id: str | None = None, timeout: int = 90) -> list[dict[str, str]] | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    with tempfile.TemporaryDirectory(prefix="safecoder_govet_") as tmp:
        root = Path(tmp)
        (root / ".tmp").mkdir(parents=True, exist_ok=True)
        (root / "go.mod").write_text("module safecoder_static\n\ngo 1.22\n", encoding="utf-8")
        source = root / "main.go"
        code_text = code or ""
        if not code_text.strip().startswith("package "):
            code_text = "package main\n\n" + code_text
        source.write_text(code_text, encoding="utf-8")
        proc = _run_command(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "-v",
                f"{root.as_posix()}:/work",
                "-w",
                "/work",
                "-e",
                "TMPDIR=/work/.tmp",
                "-e",
                "TEMP=/work/.tmp",
                "-e",
                "TMP=/work/.tmp",
                "-e",
                "GOTMPDIR=/work/.tmp",
                "golang:1.22",
                "go",
                "vet",
                "./...",
            ],
            cwd=root,
            timeout=timeout,
        )
        return parse_govet_output((proc.stdout or "") + "\n" + (proc.stderr or ""))


def run_gosec_analyzer(code: str, task_id: str | None = None, timeout: int = 120) -> list[dict[str, str]] | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    image = "securego/gosec:latest"
    with tempfile.TemporaryDirectory(prefix="safecoder_gosec_") as tmp:
        root = Path(tmp)
        (root / ".tmp").mkdir(parents=True, exist_ok=True)
        (root / "go.mod").write_text("module safecoder_static\n\ngo 1.22\n", encoding="utf-8")
        code_text = code or ""
        if not code_text.strip().startswith("package "):
            code_text = "package main\n\n" + code_text
        (root / "main.go").write_text(code_text, encoding="utf-8")
        proc = _run_command(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "-v",
                f"{root.as_posix()}:/src",
                "-w",
                "/src",
                "-e",
                "TMPDIR=/src/.tmp",
                "-e",
                "TEMP=/src/.tmp",
                "-e",
                "TMP=/src/.tmp",
                "-e",
                "GOTMPDIR=/src/.tmp",
                image,
                "-fmt=json",
                "./...",
            ],
            cwd=root,
            timeout=timeout,
        )
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return None
        return parse_gosec_warnings(payload)


def tool_static_warnings(language: str, code: str, task_id: str | None = None) -> list[dict[str, str]]:
    if language == "python":
        warnings = run_bandit_analyzer(code, task_id)
        if warnings is not None:
            return warnings
    if language == "go":
        warnings: list[dict[str, str]] = []
        vet = run_go_vet_analyzer(code, task_id)
        if vet is not None:
            warnings.extend(vet)
        gosec = run_gosec_analyzer(code, task_id)
        if gosec is not None:
            warnings.extend(gosec)
        if vet is not None or gosec is not None:
            return warnings
    # Java heavier tools (CodeQL / SpotBugs + FindSecBugs) are intentionally
    # handled as optional external tooling. Use fallback if unavailable.
    return [
        {**warning, "tool": "lightweight"}
        for warning in static_warnings(language, code)
    ]


def _warning_penalty(warnings: list[dict[str, str]], loc: int) -> tuple[float, float]:
    weights = {"low": 0.5, "medium": 1.0, "high": 2.0}
    weighted = sum(weights.get(item.get("severity", "low"), 0.5) for item in warnings)
    density = weighted / max(loc, 1)
    return min(weighted / 6.0, 1.0), density


def _complexity_penalty(complexity: int, loc: int) -> float:
    if loc <= 0:
        return 1.0
    density = complexity / max(loc, 1)
    return min(max(complexity - 12, 0) / 18 + max(density - 0.35, 0) / 0.65, 1.0)


def _growth_penalty(loc: int, source_loc: int) -> tuple[float, float | None]:
    if source_loc <= 0:
        return 0.0, None
    ratio = loc / source_loc
    return min(max(ratio - 2.0, 0) / 4.0, 1.0), ratio


def reference_code_for_growth(record: dict[str, Any], language: str, mode: str) -> tuple[str, str | None]:
    if mode not in GROWTH_BASELINE_MODES:
        raise ValueError(f"Unsupported growth baseline mode: {mode}")
    if mode == "none":
        return "", None
    if mode == "python_source":
        return str(record.get("Source Secure Code Python") or ""), "Source Secure Code Python"

    label = LANGUAGE_LABELS.get(language, language)
    candidates = [
        f"Source Secure Code {label}",
        f"Reference Secure Code {label}",
        f"Original Secure Code {label}",
        f"{label} Reference Secure Code",
        f"{label} Original Secure Code",
        "Same Language Secure Code",
        "Reference Secure Code",
        "Original Secure Code",
        "Source Secure Code",
        "Baseline Secure Code",
    ]
    for field in candidates:
        value = record.get(field)
        if value:
            return str(value), field
    return "", None


def compute_prcs(
    *,
    func_pass: bool,
    sec_pass: bool,
    warning_penalty: float,
    complexity_penalty: float,
    growth_penalty: float | None,
) -> float:
    components = [
        (0.35, float(func_pass)),
        (0.35, float(sec_pass)),
        (0.15, 1.0 - warning_penalty),
        (0.10, 1.0 - complexity_penalty),
    ]
    if growth_penalty is not None:
        components.append((0.05, 1.0 - growth_penalty))
    total_weight = sum(weight for weight, _ in components)
    score = sum(weight * value for weight, value in components) / max(total_weight, 1e-9)
    return round(max(0.0, min(1.0, score)), 4)


def compute_engineering_quality_score(
    *,
    warning_penalty: float,
    complexity_penalty: float,
    growth_penalty: float | None,
) -> float:
    components = [
        (0.50, 1.0 - warning_penalty),
        (0.30, 1.0 - complexity_penalty),
    ]
    if growth_penalty is not None:
        components.append((0.20, 1.0 - growth_penalty))
    total_weight = sum(weight for weight, _ in components)
    score = sum(weight * value for weight, value in components) / max(total_weight, 1e-9)
    return round(max(0.0, min(1.0, score)), 4)


def _validation_index(validation_rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}
    for row in validation_rows:
        if row.get("track") != "secure":
            continue
        key = (str(row.get("subset")), str(row.get("language")), str(row.get("task_id")))
        index[key] = row
    return index


def compute_record_quality(
    subset: str,
    language: str,
    record: dict[str, Any],
    validation: dict[str, Any] | None,
    warning_provider: WarningProvider | None = None,
    growth_baseline_mode: str = "none",
) -> dict[str, Any]:
    code = record.get("Secure Code") or ""
    source_code, source_field = reference_code_for_growth(record, language, growth_baseline_mode)
    loc = logical_loc(code)
    source_loc = logical_loc(source_code)
    complexity = cyclomatic_complexity(language, code)
    provider = warning_provider or (lambda lang, src, task_id=None: [{**warning, "tool": "lightweight"} for warning in static_warnings(lang, src)])
    warnings = provider(language, code, str(record.get("ID") or ""))
    warning_penalty, warning_density = _warning_penalty(warnings, loc)
    complexity_penalty = _complexity_penalty(complexity, loc)
    growth_penalty, growth_ratio = _growth_penalty(loc, source_loc)
    growth_penalty_for_score = growth_penalty if growth_ratio is not None else None
    validation_available = validation is not None
    func_pass = bool(validation and validation.get("ok"))
    sec_pass = bool(validation and validation.get("ok"))
    prcs = compute_prcs(
        func_pass=func_pass,
        sec_pass=sec_pass,
        warning_penalty=warning_penalty,
        complexity_penalty=complexity_penalty,
        growth_penalty=growth_penalty_for_score,
    )
    eqs = compute_engineering_quality_score(
        warning_penalty=warning_penalty,
        complexity_penalty=complexity_penalty,
        growth_penalty=growth_penalty_for_score,
    )
    return {
        "subset": subset,
        "language": language,
        "task_id": record.get("ID"),
        "func_pass": func_pass,
        "sec_pass": sec_pass,
        "func_sec": func_pass and sec_pass,
        "prcs": prcs,
        "eqs": eqs,
        "loc": loc,
        "source_loc": source_loc,
        "growth_baseline_mode": growth_baseline_mode,
        "growth_reference_field": source_field,
        "loc_growth_ratio": round(growth_ratio, 4) if growth_ratio is not None and math.isfinite(growth_ratio) else None,
        "growth_penalty": round(growth_penalty, 4) if growth_ratio is not None else None,
        "complexity": complexity,
        "complexity_penalty": round(complexity_penalty, 4),
        "static_warnings": len(warnings),
        "static_warning_density": round(warning_density, 6),
        "warning_penalty": round(warning_penalty, 4),
        "warnings": warnings[:20],
        "validation_ok": bool(validation and validation.get("ok")),
        "validation_available": validation_available,
    }


def compute_quality_metrics(
    records: dict[tuple[str, str], list[dict[str, Any]]],
    validation_rows: list[dict[str, Any]],
    warning_provider: WarningProvider | None = None,
    growth_baseline_mode: str = "none",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validation_by_key = _validation_index(validation_rows)
    rows: list[dict[str, Any]] = []
    for (subset, language), items in sorted(records.items()):
        for record in items:
            key = (subset, language, str(record.get("ID")))
            rows.append(compute_record_quality(
                subset,
                language,
                record,
                validation_by_key.get(key),
                warning_provider=warning_provider,
                growth_baseline_mode=growth_baseline_mode,
            ))
    return rows, summarize_quality(rows)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _mean_or_none(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summarize_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["subset"], row["language"])].append(row)
    groups = []
    for (subset, language), items in sorted(grouped.items()):
        groups.append(_summarize_items(items, subset=subset, language=language))
    return {
        "overall": _summarize_items(rows, subset="ALL", language="ALL"),
        "groups": groups,
    }


def _summarize_items(items: list[dict[str, Any]], *, subset: str, language: str) -> dict[str, Any]:
    total = len(items)
    validation_total = sum(1 for row in items if row.get("validation_available"))
    func_sec_count = sum(1 for row in items if row.get("func_sec"))
    func_count = sum(1 for row in items if row.get("func_pass"))
    sec_count = sum(1 for row in items if row.get("sec_pass"))
    return {
        "subset": subset,
        "language": language,
        "total": total,
        "validation_total": validation_total,
        "func_pass_count": func_count,
        "sec_pass_count": sec_count,
        "func_sec_count": func_sec_count,
        "func_sec_rate": round(func_sec_count / total * 100, 2) if total else 0.0,
        "validated_func_sec_rate": round(func_sec_count / validation_total * 100, 2) if validation_total else None,
        "prcs_avg": _mean([float(row.get("prcs") or 0) for row in items]),
        "eqs_avg": _mean([float(row.get("eqs") or 0) for row in items]),
        "loc_avg": _mean([float(row.get("loc") or 0) for row in items]),
        "loc_growth_avg": _mean_or_none([float(row.get("loc_growth_ratio") or 0) for row in items if row.get("loc_growth_ratio") is not None]),
        "complexity_avg": _mean([float(row.get("complexity") or 0) for row in items]),
        "static_warnings_total": sum(int(row.get("static_warnings") or 0) for row in items),
        "static_warning_density_avg": _mean([float(row.get("static_warning_density") or 0) for row in items]),
    }


def write_quality_report(output_root: Path, rows: list[dict[str, Any]], summary: dict[str, Any], growth_baseline_mode: str = "none") -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    def display(value: Any) -> Any:
        return "N/A" if value is None else value

    lines = [
        "# Production-Ready Quality Metrics Report",
        "",
        "This report adds PRCS (Production-Ready Composite Score) on top of Secure Docker validation results.",
        "",
        "PRCS = 0.35*Func + 0.35*Sec + 0.15*(1-WarningPenalty) + 0.10*(1-ComplexityPenalty) + 0.05*(1-GrowthPenalty) when a valid growth baseline exists.",
        "",
        "If GrowthPenalty is unavailable, PRCS/EQS are re-normalized over the remaining valid components instead of pretending growth is perfect.",
        "",
        "EQS (Engineering Quality Score) removes Func/Sec and isolates maintainability signals: EQS = 0.50*(1-WarningPenalty) + 0.30*(1-ComplexityPenalty) + 0.20*(1-GrowthPenalty) when a valid growth baseline exists.",
        "",
        f"Growth baseline mode: `{growth_baseline_mode}`. Use `none` for finalized SecEvoBasePlus dataset scoring, `python_source` only for direct Python-to-target generation outputs, and `same_language_reference` only when each generated row carries a same-language reference field.",
        "",
        "The current implementation is tool-first: Python uses Bandit when available; Go uses Dockerized go vet and gosec when available; Java currently falls back to built-in rules unless a Java SAST tool is configured. Lightweight rules remain the fallback.",
        "",
        "## Summary",
        "",
        "| Subset | Language | Total | Validated | Func+Sec | Func+Sec Rate | Avg PRCS | Avg EQS | Avg LoC | Avg Growth | Avg Complexity | Warnings | Avg Warning Density |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["groups"]:
        lines.append(
            f"| {item['subset']} | {LANGUAGE_LABELS.get(item['language'], item['language'])} | {item['total']} | "
            f"{item['validation_total']} | {item['func_sec_count']} | {item['func_sec_rate']}% | {item['prcs_avg']} | {item['eqs_avg']} | {item['loc_avg']} | "
            f"{display(item['loc_growth_avg'])} | {item['complexity_avg']} | {item['static_warnings_total']} | "
            f"{item['static_warning_density_avg']} |"
        )
    overall = summary["overall"]
    lines.extend([
        "",
        "## Overall",
        "",
        f"- Total: {overall['total']}",
        f"- Func+Sec: {overall['func_sec_count']} ({overall['func_sec_rate']}%)",
        f"- Avg PRCS: {overall['prcs_avg']}",
        f"- Avg EQS: {overall['eqs_avg']}",
        f"- Static warnings: {overall['static_warnings_total']}",
        "",
        "## Lowest PRCS Samples",
        "",
        "| Subset | Language | Task ID | PRCS | EQS | Func+Sec | LoC | Growth | Complexity | Warnings |",
        "|---|---|---|---:|---:|---|---:|---:|---:|---:|",
    ])
    for row in sorted(rows, key=lambda item: (float(item.get("prcs") or 0), -int(item.get("static_warnings") or 0)))[:30]:
        lines.append(
            f"| {row['subset']} | {LANGUAGE_LABELS.get(row['language'], row['language'])} | {row['task_id']} | "
            f"{row['prcs']} | {row['eqs']} | {row['func_sec']} | {row['loc']} | {row.get('loc_growth_ratio')} | "
            f"{row['complexity']} | {row['static_warnings']} |"
        )
    report = output_root / "quality_metrics_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
