from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .run_translate_dataset import process_record


RESULT_FIELDS = {
    "secure_cpp": "Secure Code C++ Test Result",
    "secure_go": "Secure Code Go Test Result",
    "insecure_cpp": "Insecure Code C++ Behavior Result",
    "insecure_go": "Insecure Code Go Behavior Result",
}


@dataclass(frozen=True)
class ExperimentSplit:
    train_records: list[dict[str, Any]]
    test_records: list[dict[str, Any]]
    train_ids: list[str]
    test_ids: list[str]


@dataclass(frozen=True)
class CrossLanguageSplit:
    train_records: list[dict[str, Any]]
    dev_records: list[dict[str, Any]]
    test_records: list[dict[str, Any]]
    train_ids: list[str]
    dev_ids: list[str]
    test_ids: list[str]


@dataclass(frozen=True)
class ArchitectureVariant:
    name: str
    max_repair_attempts: int
    use_memory: bool
    use_negative_lessons: bool = False
    use_skill_evolution: bool = False
    use_python_delta: bool = False
    use_failure_typed_repair: bool = False
    use_adaptive_memory: bool = False
    use_contrastive_dual_track: bool = False
    use_evolution_gate: bool = False
    use_verifier_guided_evolution: bool = False

    @staticmethod
    def defaults() -> list["ArchitectureVariant"]:
        return [
            ArchitectureVariant("baseline_repair", max_repair_attempts=1, use_memory=False),
            ArchitectureVariant("memory_positive", max_repair_attempts=1, use_memory=True),
            ArchitectureVariant(
                "memory_positive_negative",
                max_repair_attempts=1,
                use_memory=True,
                use_negative_lessons=True,
            ),
            ArchitectureVariant(
                "memory_skill_evolution",
                max_repair_attempts=2,
                use_memory=True,
                use_negative_lessons=True,
                use_skill_evolution=True,
            ),
        ]

    @staticmethod
    def full_method_variants() -> list["ArchitectureVariant"]:
        return [
            ArchitectureVariant("S0_direct_translation", max_repair_attempts=0, use_memory=False),
            ArchitectureVariant("S1_feedback_repair", max_repair_attempts=1, use_memory=False),
            ArchitectureVariant(
                "S2_python_delta_transfer",
                max_repair_attempts=1,
                use_memory=True,
                use_python_delta=True,
            ),
            ArchitectureVariant(
                "S3_adaptive_memory",
                max_repair_attempts=1,
                use_memory=True,
                use_python_delta=True,
                use_adaptive_memory=True,
            ),
            ArchitectureVariant(
                "S4_contrastive_dual_track",
                max_repair_attempts=1,
                use_memory=True,
                use_python_delta=True,
                use_adaptive_memory=True,
                use_contrastive_dual_track=True,
            ),
            ArchitectureVariant(
                "S5_evolution_gate",
                max_repair_attempts=2,
                use_memory=True,
                use_python_delta=True,
                use_adaptive_memory=True,
                use_contrastive_dual_track=True,
                use_evolution_gate=True,
                use_skill_evolution=True,
            ),
        ]


def build_cross_language_method_matrix() -> list[ArchitectureVariant]:
    return [
        ArchitectureVariant("M0_direct_translation", max_repair_attempts=0, use_memory=False),
        ArchitectureVariant("M1_feedback_repair", max_repair_attempts=1, use_memory=False),
        ArchitectureVariant(
            "M2_python_delta_memory",
            max_repair_attempts=1,
            use_memory=True,
            use_python_delta=True,
        ),
        ArchitectureVariant(
            "M3_failure_typed_repair",
            max_repair_attempts=1,
            use_memory=True,
            use_python_delta=True,
            use_failure_typed_repair=True,
        ),
        ArchitectureVariant(
            "M4_adaptive_retrieval",
            max_repair_attempts=1,
            use_memory=True,
            use_python_delta=True,
            use_failure_typed_repair=True,
            use_adaptive_memory=True,
        ),
        ArchitectureVariant(
            "M5_verifier_guided_evolution",
            max_repair_attempts=1,
            use_memory=True,
            use_python_delta=True,
            use_failure_typed_repair=True,
            use_adaptive_memory=True,
            use_verifier_guided_evolution=True,
        ),
        ArchitectureVariant(
            "M6_skill_evolution",
            max_repair_attempts=2,
            use_memory=True,
            use_python_delta=True,
            use_failure_typed_repair=True,
            use_adaptive_memory=True,
            use_verifier_guided_evolution=True,
            use_skill_evolution=True,
        ),
        ArchitectureVariant(
            "M7_full_method",
            max_repair_attempts=2,
            use_memory=True,
            use_python_delta=True,
            use_failure_typed_repair=True,
            use_adaptive_memory=True,
            use_contrastive_dual_track=True,
            use_evolution_gate=True,
            use_verifier_guided_evolution=True,
            use_skill_evolution=True,
        ),
    ]


def _load_records(data_path: Path) -> list[dict[str, Any]]:
    records = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected JSON array in {data_path}")
    return records


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("ID", ""))


def build_experiment_splits(data_path: Path, *, train_size: int, test_size: int, seed: int) -> ExperimentSplit:
    records = _load_records(data_path)
    if train_size < 0 or test_size < 0:
        raise ValueError("train_size and test_size must be non-negative")
    if train_size + test_size > len(records):
        raise ValueError("train_size + test_size exceeds available records")

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    train_records = shuffled[:train_size]
    test_records = shuffled[train_size : train_size + test_size]
    return ExperimentSplit(
        train_records=train_records,
        test_records=test_records,
        train_ids=[_record_id(record) for record in train_records],
        test_ids=[_record_id(record) for record in test_records],
    )


def build_cross_language_splits(
    data_path: Path,
    *,
    train_size: int,
    dev_size: int,
    test_size: int,
    seed: int,
) -> CrossLanguageSplit:
    records = _load_records(data_path)
    if train_size < 0 or dev_size < 0 or test_size < 0:
        raise ValueError("split sizes must be non-negative")
    if train_size + dev_size + test_size > len(records):
        raise ValueError("train_size + dev_size + test_size exceeds available records")

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    train_records = shuffled[:train_size]
    dev_records = shuffled[train_size : train_size + dev_size]
    test_records = shuffled[train_size + dev_size : train_size + dev_size + test_size]
    return CrossLanguageSplit(
        train_records=train_records,
        dev_records=dev_records,
        test_records=test_records,
        train_ids=[_record_id(record) for record in train_records],
        dev_ids=[_record_id(record) for record in dev_records],
        test_ids=[_record_id(record) for record in test_records],
    )


def _ok(record: dict[str, Any], field: str) -> bool:
    result = record.get(field)
    return isinstance(result, dict) and result.get("ok") is True


def summarize_architecture_results(architecture: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    counts = {
        key: sum(1 for record in records if _ok(record, field))
        for key, field in RESULT_FIELDS.items()
    }
    all_four_ok = sum(
        1
        for record in records
        if all(_ok(record, field) for field in RESULT_FIELDS.values())
    )
    secure_total = total * 2
    insecure_total = total * 2
    secure_ok = counts["secure_cpp"] + counts["secure_go"]
    insecure_ok = counts["insecure_cpp"] + counts["insecure_go"]
    return {
        "architecture": architecture,
        "records": total,
        "secure_cpp_ok": counts["secure_cpp"],
        "secure_go_ok": counts["secure_go"],
        "insecure_cpp_ok": counts["insecure_cpp"],
        "insecure_go_ok": counts["insecure_go"],
        "all_four_ok": all_four_ok,
        "secure_rate": round(secure_ok / secure_total, 4) if secure_total else 0.0,
        "insecure_rate": round(insecure_ok / insecure_total, 4) if insecure_total else 0.0,
        "all_four_rate": round(all_four_ok / total, 4) if total else 0.0,
    }


def _score_lesson(
    lesson: dict[str, Any],
    *,
    target_language: str,
    security_mode: str,
    failure_type: str | None,
) -> float:
    if str(lesson.get("target_language", "")).lower() != target_language.lower():
        return -1.0
    if str(lesson.get("security_mode", "")).lower() != security_mode.lower():
        return -1.0
    score = float(lesson.get("quality_score", 0.0))
    if failure_type and str(lesson.get("failure_type", "")).lower() == failure_type.lower():
        score += 1.0
    return score


def retrieve_lessons(
    lessons: list[dict[str, Any]],
    *,
    target_language: str,
    security_mode: str,
    failure_type: str | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    scored = [
        (_score_lesson(
            lesson,
            target_language=target_language,
            security_mode=security_mode,
            failure_type=failure_type,
        ), lesson)
        for lesson in lessons
    ]
    usable = [(score, lesson) for score, lesson in scored if score >= 0]
    usable.sort(key=lambda item: item[0], reverse=True)
    return [lesson for _, lesson in usable[:top_k]]


def _lesson_line(lesson: dict[str, Any]) -> str:
    lesson_id = str(lesson.get("lesson_id", "unknown"))
    text = str(lesson.get("text") or lesson.get("good_pattern") or lesson.get("rationale") or "").strip()
    if not text:
        text = json.dumps(lesson, ensure_ascii=False, sort_keys=True)
    return f"- [{lesson_id}] {text}"


def build_experience_context(
    *,
    positive_lessons: list[dict[str, Any]] | None = None,
    negative_lessons: list[dict[str, Any]] | None = None,
    evolved_skill: str | None = None,
    contrastive_note: str | None = None,
) -> str:
    sections: list[str] = []
    if positive_lessons:
        sections.append(
            "Verified reusable lessons:\n"
            + "\n".join(_lesson_line(lesson) for lesson in positive_lessons)
        )
    if negative_lessons:
        sections.append(
            "Warning-only negative lessons:\n"
            + "\n".join(_lesson_line(lesson) for lesson in negative_lessons)
        )
    if evolved_skill:
        sections.append(f"Evolved repair skill:\n{evolved_skill.strip()}")
    if contrastive_note:
        sections.append(f"Contrastive dual-track constraint:\n{contrastive_note.strip()}")
    if not sections:
        return ""
    return "Architecture experience context:\n" + "\n\n".join(sections)


def _cwe_from_id(record_id: str) -> str:
    if "_" in record_id:
        return record_id.split("_", 1)[0]
    return record_id


def build_seed_lessons(train_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    base_rules = [
        (
            "go",
            "secure",
            "compile_error",
            "Use one import block after package main, remove unused imports, and use double-quoted strings.",
        ),
        (
            "go",
            "insecure",
            "security_mismatch",
            "Only fix syntax/type/import issues. Do not add validation or safer APIs that the Python insecure source lacks.",
        ),
        (
            "cpp",
            "secure",
            "compile_error",
            "Use C++17, include required standard headers, avoid C++20-only APIs, and keep exactly one main in validation harnesses.",
        ),
        (
            "cpp",
            "insecure",
            "security_mismatch",
            "Preserve the vulnerable behavior while fixing target-language compile or interface errors.",
        ),
    ]
    for language, mode, failure_type, text in base_rules:
        supporting = [
            _record_id(record)
            for record in train_records
            if _ok(record, RESULT_FIELDS[f"{mode}_{language}"])
        ]
        lessons.append(
            {
                "lesson_id": f"seed-{language}-{mode}-{failure_type}",
                "target_language": language,
                "security_mode": mode,
                "failure_type": failure_type,
                "quality_score": 0.75 + min(len(supporting), 4) * 0.05,
                "text": text,
                "supporting_case_ids": supporting,
                "source": "train_seed",
            }
        )
    for record in train_records:
        cwe = _cwe_from_id(_record_id(record))
        if "CWE-078" in cwe or "CWE-077" in cwe:
            lessons.append(
                {
                    "lesson_id": f"{_record_id(record)}-command-injection",
                    "target_language": "go",
                    "security_mode": "insecure",
                    "failure_type": "security_mismatch",
                    "quality_score": 0.88,
                    "text": "For command-injection insecure examples, preserve string concatenation or shell-like unsafe composition.",
                    "supporting_case_ids": [_record_id(record)],
                    "source": "train_cwe",
                }
            )
    return lessons


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _intent_from_tags(tags: list[str], *, mode: str) -> str:
    joined = ", ".join(tags)
    if mode == "secure":
        return (
            f"Preserve the Python secure behavior for {joined}: keep the protection that "
            "rejects, escapes, normalizes, parameterizes, safely parses, or avoids unsafe APIs."
        )
    return (
        f"Preserve the Python insecure behavior for {joined}: keep the missing protection or "
        "unsafe operation so Go/C++ fail in the same security-relevant way."
    )


def _target_language_risks(tags: list[str]) -> dict[str, list[str]]:
    risks = {
        "go": [
            "unused imports and unused variables are compile errors",
            "use one import block after package main",
            "avoid third-party modules unless the sandbox explicitly installs them",
        ],
        "cpp": [
            "keep code C++17-compatible",
            "include all standard headers used by helpers",
            "avoid third-party headers and C++20-only APIs",
        ],
    }
    if "command_injection" in tags:
        risks["go"].append("model command execution with standard-library strings or os/exec only when needed")
        risks["cpp"].append("avoid real shell execution in validation harnesses; use observable string behavior when possible")
    if "deserialization" in tags or "xml_parsing" in tags:
        risks["go"].append("use standard-library parsers or small local parsers instead of external YAML/XML modules")
        risks["cpp"].append("use a small local parser or string checks instead of libxml/nlohmann/json")
    if "path_traversal" in tags:
        risks["go"].append("preserve or reject traversal according to secure/insecure mode without changing mode semantics")
        risks["cpp"].append("use std::filesystem for secure mode; do not silently canonicalize insecure mode")
    return risks


def build_security_delta_cards(train_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for record in train_records:
        record_id = _record_id(record)
        tags = _infer_security_tags(record)
        cards.append(
            {
                "card_id": f"card-{record_id}",
                "card_type": "security_delta_card",
                "source": "python_train",
                "case_id": record_id,
                "cwe": _cwe_from_id(record_id),
                "tags": tags,
                "secure_intent": _intent_from_tags(tags, mode="secure"),
                "insecure_intent": _intent_from_tags(tags, mode="insecure"),
                "secure_pattern": _compact_pattern(str(record.get("Secure Code", ""))),
                "insecure_pattern": _compact_pattern(str(record.get("Insecure Code", ""))),
                "oracle_hint": _compact_pattern(str(record.get("Test", ""))),
                "target_language_risks": _target_language_risks(tags),
                "allowed_modes": ["secure", "insecure"],
                "status": "candidate",
            }
        )
    return cards


def classify_failure_type(result: dict[str, Any]) -> str:
    details = result.get("details") if isinstance(result.get("details"), dict) else {}
    detail_type = str(details.get("error_type") or result.get("error_type") or "").lower()
    stderr = str(result.get("stderr", "")).lower()
    error = str(result.get("error", "")).lower()
    combined = "\n".join([detail_type, stderr, error])
    if "timeout" in combined:
        return "timeout"
    if (
        "compile" in combined
        or "syntax error" in combined
        or "imported and not used" in combined
        or "declared and not used" in combined
        or "undefined:" in combined
        or "no required module" in combined
        or "fatal error:" in combined
    ):
        return "compile_error"
    if "security_mismatch" in combined or "vulnerability" in combined or "became safe" in combined:
        return "security_mismatch"
    if "functional" in combined or "assert" in combined or "expected" in combined:
        return "functional_mismatch"
    if "runtime" in combined or "panic" in combined or "exception" in combined:
        return "runtime_error"
    return "unknown_failure"


def make_adaptive_repair_strategy(language_code: str, mode: str, failure_type: str) -> str:
    language = language_code.lower()
    mode = mode.lower()
    failure_type = failure_type.lower()
    rules: list[str] = []
    if language == "go":
        rules.append("Go: fix unused imports, unused variables, undefined symbols, import placement, and string quotes first.")
        rules.append("Go: keep only standard-library dependencies unless the sandbox installs a module explicitly.")
    elif language == "cpp":
        rules.append("C++: keep the fix C++17-compatible, include missing headers, and avoid C++20-only APIs.")
        rules.append("C++: prefer small helper functions at namespace scope over large rewrites.")
    if failure_type == "compile_error":
        rules.append("Compile repair: change the smallest syntax/import/type/interface surface that makes the code build.")
    elif failure_type == "security_mismatch":
        if mode == "insecure":
            rules.append("Insecure repair: do not add validation, escaping, safer APIs, canonicalization, or parameterization.")
            rules.append("Insecure repair: preserve the Python bad behavior; only fix target-language translation mistakes.")
        else:
            rules.append("Secure repair: restore the missing protection from the Python secure source.")
    elif failure_type == "functional_mismatch":
        rules.append("Functional repair: match the Python check(candidate) behavior without changing security mode.")
    elif failure_type == "timeout":
        rules.append("Timeout repair: remove blocking loops, real network calls, and long sleeps; keep behavior testable.")
    else:
        rules.append("Unknown failure repair: classify compile/interface issues before changing algorithmic behavior.")
    return " ".join(rules)


def _compact_pattern(code: str, *, max_len: int = 220) -> str:
    compact = " ".join(code.split())
    return compact[:max_len]


def _infer_security_tags(record: dict[str, Any]) -> list[str]:
    combined = "\n".join(
        str(record.get(field, ""))
        for field in ("Problem", "Secure Code", "Insecure Code", "Test")
    )
    tags: list[str] = []
    checks: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("command_injection", ("os.system", "os.popen", "subprocess", "shell", "command")),
        ("path_traversal", ("../", "path", "filepath", "filesystem", "open(")),
        ("sql_injection", ("sql", "select", "execute(", "query")),
        ("deserialization", ("pickle", "yaml", "deserialize", "loads(")),
        ("xss_output_encoding", ("html", "escape", "script", "xss")),
        ("crypto_randomness", ("crypto", "random", "aes", "md5", "sha1", "iv")),
        ("xml_parsing", ("xml", "xxe", "entity", "etree")),
        ("input_validation", ("validate", "sanitize", "assert_raises", "valueerror")),
    )
    for tag, needles in checks:
        if _contains_any(combined, needles):
            tags.append(tag)
    return tags or ["generic_security"]


def build_python_delta_memory(train_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    memories: list[dict[str, Any]] = []
    for record in train_records:
        record_id = _record_id(record)
        cwe = _cwe_from_id(record_id)
        secure_code = str(record.get("Secure Code", ""))
        insecure_code = str(record.get("Insecure Code", ""))
        test_code = str(record.get("Test", ""))
        tags = _infer_security_tags(record)
        memories.append(
            {
                "memory_id": f"delta-{record_id}",
                "source": "python_train",
                "cwe": cwe,
                "security_mode": "both",
                "target_language": "generic",
                "memory_type": "delta",
                "tags": tags,
                "trigger": f"Python secure/insecure pair for {cwe}",
                "secure_pattern": _compact_pattern(secure_code),
                "insecure_pattern": _compact_pattern(insecure_code),
                "target_rule": (
                    "Secure target translations should preserve the secure pattern; insecure target "
                    "translations should preserve the insecure behavior captured by the Python tests."
                ),
                "validation_hint": _compact_pattern(test_code),
                "evidence_ids": [record_id],
                "status": "candidate",
                "quality_score": 0.7,
            }
        )
    return memories


def delta_memory_to_lessons(delta_memory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    for memory in delta_memory:
        for language in ("go", "cpp"):
            for mode in ("secure", "insecure"):
                if mode == "secure":
                    text = (
                        "Transfer Python secure pattern to target language. "
                        f"Tags: {', '.join(memory.get('tags', []))}. "
                        f"Secure pattern: {memory.get('secure_pattern', '')}"
                    )
                else:
                    text = (
                        "Preserve Python insecure behavior in target language. "
                        f"Tags: {', '.join(memory.get('tags', []))}. "
                        f"Insecure pattern: {memory.get('insecure_pattern', '')}"
                    )
                lessons.append(
                    {
                        "lesson_id": f"{memory['memory_id']}-{language}-{mode}",
                        "target_language": language,
                        "security_mode": mode,
                        "failure_type": "security_mismatch",
                        "quality_score": memory.get("quality_score", 0.7),
                        "text": text,
                        "supporting_case_ids": memory.get("evidence_ids", []),
                        "source": "python_delta_memory",
                        "memory_type": "delta",
                        "tags": memory.get("tags", []),
                        "status": memory.get("status", "candidate"),
                    }
                )
    return lessons


def evolution_gate(
    candidate_lessons: list[dict[str, Any]],
    dev_results: list[dict[str, Any]],
    *,
    min_support: int = 1,
    max_failures: int = 0,
) -> list[dict[str, Any]]:
    dev_success_ids = {
        _record_id(record)
        for record in dev_results
        if any(_ok(record, field) for field in RESULT_FIELDS.values())
    }
    promoted: list[dict[str, Any]] = []
    for lesson in candidate_lessons:
        supporting = set(str(case_id) for case_id in lesson.get("supporting_case_ids", []))
        support_count = len(supporting & dev_success_ids) if dev_success_ids else len(supporting)
        failure_count = int(lesson.get("failure_count", 0))
        if support_count >= min_support and failure_count <= max_failures:
            updated = dict(lesson)
            updated["status"] = "verified"
            updated["quality_score"] = max(float(updated.get("quality_score", 0.0)), 0.85)
            promoted.append(updated)
    return promoted


def _track_result(record: dict[str, Any], language: str, mode: str) -> dict[str, Any] | None:
    field = RESULT_FIELDS.get(f"{mode}_{language}")
    if field is None:
        return None
    result = record.get(field)
    if isinstance(result, dict):
        return result
    return None


def gate_lessons_with_dev_results(
    candidate_lessons: list[dict[str, Any]],
    dev_results: list[dict[str, Any]],
    *,
    min_track_successes: int = 1,
    max_track_failures: int = 0,
) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    for lesson in candidate_lessons:
        language = str(lesson.get("target_language", "")).lower()
        mode = str(lesson.get("security_mode", "")).lower()
        if language not in {"go", "cpp"} or mode not in {"secure", "insecure"}:
            continue
        successes = 0
        failures = 0
        failure_types: dict[str, int] = {}
        for record in dev_results:
            result = _track_result(record, language, mode)
            if result is None:
                continue
            if result.get("ok") is True:
                successes += 1
            else:
                failures += 1
                failure_type = classify_failure_type(result)
                failure_types[failure_type] = failure_types.get(failure_type, 0) + 1
        if successes >= min_track_successes and failures <= max_track_failures:
            updated = dict(lesson)
            updated["status"] = "verified_by_dev"
            updated["dev_support"] = successes
            updated["dev_failures"] = failures
            updated["dev_failure_types"] = failure_types
            updated["quality_score"] = max(float(updated.get("quality_score", 0.0)), 0.9)
            promoted.append(updated)
    return promoted


def build_evolved_skill(train_records: list[dict[str, Any]]) -> str:
    cwes = sorted({_cwe_from_id(_record_id(record)) for record in train_records})
    return (
        "Before changing behavior, classify the failure as compile/interface, functional mismatch, "
        "or security-semantics mismatch. Prefer the smallest target-language fix. For insecure mode, "
        "never convert a vulnerable API or missing validation into a secure alternative unless the "
        "Python insecure source already did so. Training CWEs observed: "
        + ", ".join(cwes[:8])
        + "."
    )


def make_experience_provider(
    variant: ArchitectureVariant,
    lessons: list[dict[str, Any]],
    evolved_skill: str,
):
    if not variant.use_memory:
        return None

    def provider(record: dict[str, Any], language_code: str, mode: str, stage: str) -> str:
        if stage == "translation":
            return ""
        result_key = RESULT_FIELDS.get(f"{mode}_{language_code}")
        observed_failure_type = None
        if result_key:
            result = record.get(result_key)
            if isinstance(result, dict) and result.get("pending") is not True:
                observed_failure_type = classify_failure_type(result)
        if variant.use_adaptive_memory:
            cwe = _cwe_from_id(_record_id(record))
            tags = set(_infer_security_tags(record))
            relevant_lessons = [
                lesson
                for lesson in lessons
                if (
                    lesson.get("cwe") == cwe
                    or tags.intersection(set(lesson.get("tags", [])))
                    or lesson.get("memory_type") != "delta"
                )
            ]
        else:
            relevant_lessons = lessons
        positive = retrieve_lessons(
            relevant_lessons,
            target_language=language_code,
            security_mode=mode,
            failure_type=observed_failure_type,
            top_k=3,
        )
        negative: list[dict[str, Any]] = []
        if variant.use_negative_lessons:
            opposite_mode = "insecure" if mode == "secure" else "secure"
            negative = retrieve_lessons(
                relevant_lessons,
                target_language=language_code,
                security_mode=opposite_mode,
                failure_type=None,
                top_k=1,
            )
        contrastive_note = None
        if variant.use_contrastive_dual_track:
            if mode == "secure":
                contrastive_note = (
                    "Compare against the Python insecure behavior and avoid translating the "
                    "secure solution into the vulnerable pattern."
                )
            else:
                contrastive_note = (
                    "Compare against the Python secure behavior and do not accidentally repair "
                    "the intentionally insecure target."
                )
        strategy = None
        if variant.use_failure_typed_repair:
            strategy = make_adaptive_repair_strategy(
                language_code,
                mode,
                observed_failure_type or "unknown_failure",
            )
            if contrastive_note:
                contrastive_note = f"{contrastive_note}\nFailure-typed repair strategy: {strategy}"
            else:
                contrastive_note = f"Failure-typed repair strategy: {strategy}"
        return build_experience_context(
            positive_lessons=positive,
            negative_lessons=negative,
            evolved_skill=evolved_skill if variant.use_skill_evolution else None,
            contrastive_note=contrastive_note,
        )

    return provider


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_architecture_variant(
    variant: ArchitectureVariant,
    *,
    test_records: list[dict[str, Any]],
    lessons: list[dict[str, Any]],
    evolved_skill: str,
    model: str,
    request_timeout: int,
    max_tokens: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provider = make_experience_provider(variant, lessons, evolved_skill)
    outputs: list[dict[str, Any]] = []
    started = time.monotonic()
    for record in test_records:
        outputs.append(
            process_record(
                record,
                model=model,
                max_repair_attempts=variant.max_repair_attempts,
                request_timeout=request_timeout,
                max_tokens=max_tokens,
                experience_provider=provider,
            )
        )
    elapsed = round(time.monotonic() - started, 2)
    summary = summarize_architecture_results(variant.name, outputs)
    summary["elapsed_seconds"] = elapsed
    summary["max_repair_attempts"] = variant.max_repair_attempts
    summary["use_memory"] = variant.use_memory
    summary["use_negative_lessons"] = variant.use_negative_lessons
    summary["use_skill_evolution"] = variant.use_skill_evolution
    return outputs, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and summarize small architecture experiments.")
    parser.add_argument("--data-path", required=True, type=Path)
    parser.add_argument("--train-size", type=int, default=4)
    parser.add_argument("--dev-size", type=int, default=0)
    parser.add_argument("--test-size", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-api", action="store_true")
    parser.add_argument("--model", default="glm-5.1")
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--architectures", help="Comma-separated architecture names to run.")
    parser.add_argument("--full-methods", action="store_true", help="Use train/dev/test splits and S0-S5 variants.")
    parser.add_argument(
        "--method-matrix",
        action="store_true",
        help="Use the paper-grade Python-train to Go/C++-test M0-M7 method matrix.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.full_methods or args.method_matrix:
        split = build_cross_language_splits(
            args.data_path,
            train_size=args.train_size,
            dev_size=args.dev_size,
            test_size=args.test_size,
            seed=args.seed,
        )
        dev_records = split.dev_records
        dev_ids = split.dev_ids
        test_records = split.test_records
        test_ids = split.test_ids
        variants = build_cross_language_method_matrix() if args.method_matrix else ArchitectureVariant.full_method_variants()
    else:
        split = build_experiment_splits(
            args.data_path,
            train_size=args.train_size,
            test_size=args.test_size,
            seed=args.seed,
        )
        dev_records = []
        dev_ids = []
        test_records = split.test_records
        test_ids = split.test_ids
        variants = ArchitectureVariant.defaults()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "data_path": str(args.data_path),
        "train_size": len(split.train_records),
        "dev_size": len(dev_records),
        "test_size": len(test_records),
        "seed": args.seed,
        "train_ids": split.train_ids,
        "dev_ids": dev_ids,
        "test_ids": test_ids,
        "architectures": [variant.__dict__ for variant in variants],
        "dry_run": args.dry_run,
        "run_api": args.run_api,
        "model": args.model,
        "full_methods": args.full_methods,
        "method_matrix": args.method_matrix,
    }
    security_delta_cards = build_security_delta_cards(split.train_records)
    python_delta_memory = build_python_delta_memory(split.train_records)
    lessons = build_seed_lessons(split.train_records) + delta_memory_to_lessons(python_delta_memory)
    for card in security_delta_cards:
        for language in ("go", "cpp"):
            for mode in ("secure", "insecure"):
                intent = card["secure_intent"] if mode == "secure" else card["insecure_intent"]
                lessons.append(
                    {
                        "lesson_id": f"{card['card_id']}-{language}-{mode}",
                        "target_language": language,
                        "security_mode": mode,
                        "failure_type": "security_mismatch",
                        "quality_score": 0.78,
                        "text": (
                            f"{intent} Target risks: "
                            + "; ".join(card["target_language_risks"].get(language, []))
                        ),
                        "supporting_case_ids": [card["case_id"]],
                        "source": "security_delta_card",
                        "memory_type": "delta_card",
                        "tags": card["tags"],
                        "status": card["status"],
                    }
                )
    if args.full_methods and dev_records:
        lessons = evolution_gate(lessons, dev_records, min_support=0, max_failures=0)
    if args.method_matrix and dev_records:
        dev_verified = gate_lessons_with_dev_results(
            lessons,
            dev_records,
            min_track_successes=1,
            max_track_failures=0,
        )
        if dev_verified:
            verified_ids = {lesson["lesson_id"] for lesson in dev_verified}
            lessons = [
                lesson
                for lesson in lessons
                if (
                    lesson.get("source") in {"train_seed", "python_delta_memory", "security_delta_card"}
                    and not lesson.get("lesson_id", "").startswith("card-")
                )
                or lesson.get("lesson_id") in verified_ids
            ]
            lessons.extend(
                lesson
                for lesson in dev_verified
                if lesson.get("lesson_id") not in {item.get("lesson_id") for item in lessons}
            )
    evolved_skill = build_evolved_skill(split.train_records)
    manifest["lessons_path"] = str(args.output_dir / "lessons.json")
    manifest["security_delta_cards_path"] = str(args.output_dir / "security_delta_cards.json")
    manifest["python_delta_memory_path"] = str(args.output_dir / "python_delta_memory.json")
    manifest["evolved_skill"] = evolved_skill
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_json(args.output_dir / "train_records.json", split.train_records)
    _write_json(args.output_dir / "dev_records.json", dev_records)
    _write_json(args.output_dir / "test_records.json", test_records)
    _write_json(args.output_dir / "security_delta_cards.json", security_delta_cards)
    _write_json(args.output_dir / "python_delta_memory.json", python_delta_memory)
    _write_json(args.output_dir / "lessons.json", lessons)

    if args.run_api:
        selected_names = None
        if args.architectures:
            selected_names = {name.strip() for name in args.architectures.split(",") if name.strip()}
        summaries: list[dict[str, Any]] = []
        for variant in variants:
            if selected_names is not None and variant.name not in selected_names:
                continue
            records, summary = run_architecture_variant(
                variant,
                test_records=test_records,
                lessons=lessons,
                evolved_skill=evolved_skill,
                model=args.model,
                request_timeout=args.request_timeout,
                max_tokens=args.max_tokens,
            )
            _write_json(args.output_dir / f"{variant.name}.records.json", records)
            _write_json(args.output_dir / f"{variant.name}.summary.json", summary)
            summaries.append(summary)
        _write_json(args.output_dir / "comparison_report.json", summaries)
        manifest["comparison_report_path"] = str(args.output_dir / "comparison_report.json")
        _write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
