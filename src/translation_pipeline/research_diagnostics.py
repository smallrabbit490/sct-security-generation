from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


RESULT_FIELDS = (
    "Secure Code C++ Test Result",
    "Secure Code Go Test Result",
    "Insecure Code C++ Behavior Result",
    "Insecure Code Go Behavior Result",
)

TRACK_NAMES = {
    "Secure Code C++ Test Result": "secure_cpp",
    "Secure Code Go Test Result": "secure_go",
    "Insecure Code C++ Behavior Result": "insecure_cpp",
    "Insecure Code Go Behavior Result": "insecure_go",
}


def _ok(record: dict[str, Any], field: str) -> bool:
    result = record.get(field)
    return isinstance(result, dict) and result.get("ok") is True


def _score_record(record: dict[str, Any]) -> int:
    return sum(1 for field in RESULT_FIELDS if _ok(record, field))


def _all_four(record: dict[str, Any]) -> bool:
    return _score_record(record) == len(RESULT_FIELDS)


def compute_oracle_router(architecture_records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not architecture_records:
        return {"records": 0, "all_four_ok": 0, "all_four_rate": 0.0, "choices": []}

    records_by_arch = {
        arch: {str(record.get("ID")): record for record in records}
        for arch, records in architecture_records.items()
    }
    ordered_ids = list(next(iter(records_by_arch.values())).keys())
    choices: list[dict[str, Any]] = []
    routed_records: list[dict[str, Any]] = []
    for record_id in ordered_ids:
        candidates = [
            (arch, records[record_id])
            for arch, records in records_by_arch.items()
            if record_id in records
        ]
        if not candidates:
            continue
        best_arch, best_record = max(
            candidates,
            key=lambda item: (_score_record(item[1]), item[0]),
        )
        choices.append({"ID": record_id, "architecture": best_arch, "score": _score_record(best_record)})
        routed_records.append(best_record)

    all_four_ok = sum(1 for record in routed_records if _all_four(record))
    total = len(routed_records)
    return {
        "records": total,
        "all_four_ok": all_four_ok,
        "all_four_rate": round(all_four_ok / total, 4) if total else 0.0,
        "mean_track_score": round(sum(_score_record(record) for record in routed_records) / (total * 4), 4) if total else 0.0,
        "choices": choices,
    }


def analyze_track_outcomes(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    tracks: dict[str, dict[str, Any]] = {}
    for field in RESULT_FIELDS:
        name = TRACK_NAMES[field]
        ok_count = sum(1 for record in records if _ok(record, field))
        tracks[name] = {
            "ok": ok_count,
            "failed": total - ok_count,
            "rate": round(ok_count / total, 4) if total else 0.0,
        }
    if not tracks:
        weakest_tracks: list[str] = []
    else:
        lowest_rate = min(track["rate"] for track in tracks.values())
        weakest_tracks = [
            name
            for name, track in tracks.items()
            if track["rate"] == lowest_rate
        ]
    return {
        "records": total,
        "tracks": tracks,
        "weakest_tracks": weakest_tracks,
    }


def _result_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    parts = [
        str(result.get("error_type", "")),
        str(result.get("stderr", "")),
        str(result.get("stdout", "")),
        str(result.get("message", "")),
        str(result.get("error", "")),
    ]
    details = result.get("details")
    if isinstance(details, dict):
        parts.extend(str(value) for value in details.values())
    return "\n".join(parts).lower()


def _classify_failure(track_name: str, result: Any) -> str:
    text = _result_text(result)
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "imported and not used" in text:
        return "go_unused_import"
    if "undefined:" in text or "undefined " in text:
        return "go_undefined_symbol" if track_name.endswith("_go") else "undefined_symbol"
    if "no required module provides package" in text or "cannot find package" in text:
        return "go_missing_module"
    if "syntax error" in text:
        return "go_syntax_error" if track_name.endswith("_go") else "syntax_error"
    if "compile_error" in text or "error:" in text or "not declared" in text:
        return "cpp_compile_error" if track_name.endswith("_cpp") else "compile_error"
    if "runtime_error" in text or "panic:" in text or "exception" in text:
        return "runtime_error"
    if "security" in text or "mismatch" in text or "expected" in text:
        return "behavior_mismatch"
    return "unknown_failure"


def _increment_bucket(bucket: dict[str, dict[str, Any]], key: str, record_id: str, track_name: str) -> None:
    item = bucket.setdefault(key, {"count": 0, "examples": []})
    item["count"] += 1
    if len(item["examples"]) < 5:
        item["examples"].append({"ID": record_id, "track": track_name})


def analyze_failure_atlas(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    by_track: dict[str, dict[str, Any]] = {}
    failures = 0
    for record in records:
        record_id = str(record.get("ID"))
        for field in RESULT_FIELDS:
            if _ok(record, field):
                continue
            result = record.get(field)
            if not isinstance(result, dict):
                continue
            track_name = TRACK_NAMES[field]
            category = _classify_failure(track_name, result)
            failures += 1
            _increment_bucket(by_category, category, record_id, track_name)
            _increment_bucket(by_track, track_name, record_id, category)
    return {
        "records": len(records),
        "failures": failures,
        "by_category": dict(sorted(by_category.items())),
        "by_track": dict(sorted(by_track.items())),
    }


REPAIR_POLICY_TEMPLATES: dict[str, dict[str, Any]] = {
    "cpp_compile_error": {
        "allowed_change_scope": "includes_types_signatures_only",
        "constraints": [
            "Do not rewrite security logic",
            "Keep function names and public signatures aligned with tests",
            "Prefer minimal include/type/signature fixes",
        ],
    },
    "compile_error": {
        "allowed_change_scope": "syntax_imports_types_only",
        "constraints": [
            "Do not rewrite security logic",
            "Keep the original secure/insecure intent unchanged",
            "Prefer the smallest compiling change",
        ],
    },
    "go_unused_import": {
        "allowed_change_scope": "imports_only",
        "constraints": [
            "Remove unused imports only",
            "Do not change function bodies",
        ],
    },
    "go_undefined_symbol": {
        "allowed_change_scope": "imports_dependencies_api_names_only",
        "constraints": [
            "Map undefined APIs to available Go APIs",
            "Do not change the security delta",
            "Avoid adding unnecessary third-party dependencies",
        ],
    },
    "go_missing_module": {
        "allowed_change_scope": "dependency_or_standard_library_mapping_only",
        "constraints": [
            "Prefer standard library replacements",
            "Only add a dependency when the sandbox can install it",
            "Do not change the security delta",
        ],
    },
    "go_syntax_error": {
        "allowed_change_scope": "syntax_only",
        "constraints": [
            "Fix Go syntax without changing behavior",
            "Do not add new validation logic",
        ],
    },
    "runtime_error": {
        "allowed_change_scope": "minimal_runtime_fix",
        "constraints": [
            "Fix boundary, return, or exception behavior only where needed",
            "Avoid broad rewrites",
            "Keep the secure/insecure intent unchanged",
        ],
    },
    "timeout": {
        "allowed_change_scope": "termination_and_input_bounds_only",
        "constraints": [
            "Add termination bounds or reduce loops",
            "Do not alter the security delta",
        ],
    },
    "behavior_mismatch": {
        "secure_allowed_change_scope": "security_guard_logic",
        "insecure_allowed_change_scope": "preserve_expected_vulnerable_behavior",
        "constraints": [
            "For Secure, add or repair only the intended guard",
            "For Insecure, do not add security guards that remove the expected vulnerable behavior",
            "Use paired oracle feedback before accepting the repair",
        ],
    },
    "unknown_failure": {
        "allowed_change_scope": "diagnose_before_repair",
        "constraints": [
            "Classify the concrete failure before editing",
            "Prefer a small diagnostic rerun over broad rewriting",
        ],
    },
}


def synthesize_repair_policy(failure_atlas: dict[str, Any]) -> dict[str, Any]:
    by_category = failure_atlas.get("by_category", {})
    rules: dict[str, dict[str, Any]] = {}
    for category, item in sorted(by_category.items()):
        template = REPAIR_POLICY_TEMPLATES.get(category, REPAIR_POLICY_TEMPLATES["unknown_failure"])
        rules[category] = {
            **template,
            "count": int(item.get("count", 0)) if isinstance(item, dict) else 0,
        }
    return {
        "rules": rules,
        "rule_count": len(rules),
    }


def compute_router_regret(
    architecture_records: dict[str, list[dict[str, Any]]],
    oracle_report: dict[str, Any],
) -> dict[str, Any]:
    oracle_rate = float(oracle_report.get("all_four_rate", 0.0))
    architectures: dict[str, dict[str, Any]] = {}
    for architecture, records in architecture_records.items():
        total = len(records)
        all_four_ok = sum(1 for record in records if _all_four(record))
        all_four_rate = round(all_four_ok / total, 4) if total else 0.0
        architectures[architecture] = {
            "records": total,
            "all_four_ok": all_four_ok,
            "all_four_rate": all_four_rate,
            "router_regret": round(oracle_rate - all_four_rate, 4),
        }
    return {
        "oracle_all_four_rate": oracle_rate,
        "architectures": architectures,
    }


def simulate_track_router(architecture_records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not architecture_records:
        return {
            "records": 0,
            "policy": {},
            "all_four_ok": 0,
            "all_four_rate": 0.0,
            "track_rates": {},
        }

    policy: dict[str, str] = {}
    track_rates: dict[str, float] = {}
    for field in RESULT_FIELDS:
        track_name = TRACK_NAMES[field]
        best_architecture = ""
        best_rate = -1.0
        for architecture, records in architecture_records.items():
            total = len(records)
            rate = (sum(1 for record in records if _ok(record, field)) / total) if total else 0.0
            if rate > best_rate or (rate == best_rate and architecture > best_architecture):
                best_architecture = architecture
                best_rate = rate
        policy[track_name] = best_architecture
        track_rates[track_name] = round(best_rate, 4)

    records_by_arch = {
        arch: {str(record.get("ID")): record for record in records}
        for arch, records in architecture_records.items()
    }
    ordered_ids = list(next(iter(records_by_arch.values())).keys())
    all_four_ok = 0
    routed_items: list[dict[str, Any]] = []
    for record_id in ordered_ids:
        track_results: dict[str, bool] = {}
        for field in RESULT_FIELDS:
            track_name = TRACK_NAMES[field]
            architecture = policy[track_name]
            record = records_by_arch.get(architecture, {}).get(record_id)
            track_results[track_name] = _ok(record, field) if record else False
        if all(track_results.values()):
            all_four_ok += 1
        routed_items.append({"ID": record_id, "tracks": track_results})

    total_records = len(ordered_ids)
    return {
        "records": total_records,
        "policy": policy,
        "all_four_ok": all_four_ok,
        "all_four_rate": round(all_four_ok / total_records, 4) if total_records else 0.0,
        "track_rates": track_rates,
        "items": routed_items,
    }


def analyze_paired_outcomes(records: list[dict[str, Any]]) -> dict[str, Any]:
    language_fields = {
        "cpp": (
            "Secure Code C++ Test Result",
            "Insecure Code C++ Behavior Result",
        ),
        "go": (
            "Secure Code Go Test Result",
            "Insecure Code Go Behavior Result",
        ),
    }
    languages: dict[str, dict[str, Any]] = {}
    for language, (secure_field, insecure_field) in language_fields.items():
        counts = {
            "both_ok": 0,
            "secure_only": 0,
            "insecure_only": 0,
            "both_fail": 0,
        }
        items: list[dict[str, Any]] = []
        for record in records:
            secure_ok = _ok(record, secure_field)
            insecure_ok = _ok(record, insecure_field)
            if secure_ok and insecure_ok:
                category = "both_ok"
            elif secure_ok:
                category = "secure_only"
            elif insecure_ok:
                category = "insecure_only"
            else:
                category = "both_fail"
            counts[category] += 1
            items.append(
                {
                    "ID": str(record.get("ID")),
                    "secure_ok": secure_ok,
                    "insecure_ok": insecure_ok,
                    "category": category,
                }
            )
        total = len(records)
        languages[language] = {
            **counts,
            "pair_success_rate": round(counts["both_ok"] / total, 4) if total else 0.0,
            "items": items,
        }
    return {
        "records": len(records),
        "languages": languages,
    }


def _action_for_pair(category: str, diff_preserved: bool) -> tuple[str, str]:
    if category == "both_ok" and diff_preserved:
        return "accept_pair", "Secure and Insecure both satisfy their oracles and the language delta is preserved."
    if category == "both_ok":
        return "repair_delta", "Both oracles pass, but Secure/Insecure delta appears collapsed."
    if category == "secure_only":
        return "repair_insecure", "Secure passes but Insecure does not preserve the expected behavior."
    if category == "insecure_only":
        return "repair_secure", "Insecure behavior is preserved but Secure does not pass."
    return "repair_both", "Both Secure and Insecure fail for this language pair."


def plan_paired_repair_actions(
    paired_outcomes: dict[str, Any],
    delta_irs: dict[str, Any],
) -> dict[str, Any]:
    delta_by_id = {
        str(item.get("ID")): item
        for item in delta_irs.get("items", [])
        if isinstance(item, dict)
    }
    language_plans: dict[str, Any] = {}
    for language, language_report in paired_outcomes.get("languages", {}).items():
        items: list[dict[str, Any]] = []
        by_action: dict[str, int] = {}
        for item in language_report.get("items", []):
            record_id = str(item.get("ID"))
            delta = delta_by_id.get(record_id, {})
            language_delta = delta.get("target_language_delta", {}).get(language, {})
            diff_preserved = bool(language_delta.get("diff_preserved", False))
            action, reason = _action_for_pair(str(item.get("category")), diff_preserved)
            by_action[action] = by_action.get(action, 0) + 1
            items.append(
                {
                    "ID": record_id,
                    "language": language,
                    "category": item.get("category"),
                    "diff_preserved": diff_preserved,
                    "action": action,
                    "reason": reason,
                }
            )
        language_plans[language] = {
            "items": items,
            "by_action": dict(sorted(by_action.items())),
        }
    return {
        "records": paired_outcomes.get("records", 0),
        "languages": language_plans,
    }


SECURITY_TOKENS = {
    "command": ("system", "exec", "shell", "popen", "cmd", "command"),
    "validation": ("validate", "sanitize", "escape", "canonical", "normalize", "allowlist", "parameter"),
    "parsing": ("xml", "yaml", "json", "pickle", "deserialize", "entity"),
    "crypto": ("md5", "sha1", "random", "crypto", "hash", "cipher"),
    "path": ("path", "file", "dir", "open", "read", "write"),
}


def _normalize_code_shape(code: str) -> set[str]:
    lowered = code.lower()
    tokens: set[str] = set()
    for group, needles in SECURITY_TOKENS.items():
        if any(needle in lowered for needle in needles):
            tokens.add(group)
    identifier_tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", lowered)
    for token in identifier_tokens:
        if token in {"safe", "unsafe", "secure", "insecure", "validate", "sanitize", "escape"}:
            tokens.add(token)
    return tokens


def _diff_preserved_for_language(record: dict[str, Any], language_label: str) -> bool:
    if language_label == "cpp":
        secure_code = str(record.get("Secure Code C++", ""))
        insecure_code = str(record.get("Insecure Code C++", ""))
    else:
        secure_code = str(record.get("Secure Code Go", ""))
        insecure_code = str(record.get("Insecure Code Go", ""))
    if not secure_code.strip() or not insecure_code.strip():
        return False
    secure_shape = _normalize_code_shape(secure_code)
    insecure_shape = _normalize_code_shape(insecure_code)
    return secure_shape != insecure_shape


def analyze_diff_preservation(records: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for record in records:
        collapsed_languages = [
            language
            for language in ("cpp", "go")
            if not _diff_preserved_for_language(record, language)
        ]
        items.append(
            {
                "ID": str(record.get("ID")),
                "diff_preserved": not collapsed_languages,
                "collapsed_languages": collapsed_languages,
            }
        )
    preserved = sum(1 for item in items if item["diff_preserved"])
    total = len(items)
    return {
        "records": total,
        "diff_preserved": preserved,
        "diff_preservation_rate": round(preserved / total, 4) if total else 0.0,
        "items": items,
    }


def _extract_cwe(record_id: str) -> str | None:
    match = re.search(r"CWE-\d+", record_id)
    return match.group(0) if match else None


def _security_profile(code: str) -> dict[str, Any]:
    groups = _normalize_code_shape(code)
    lowered = code.lower()
    explicit_tokens = sorted(
        token
        for token in {"safe", "unsafe", "secure", "insecure", "validate", "sanitize", "escape"}
        if token in lowered
    )
    return {
        "groups": sorted(groups),
        "tokens": explicit_tokens,
    }


def _contrastive_delta(secure_code: str, insecure_code: str) -> dict[str, Any]:
    secure_profile = _security_profile(secure_code)
    insecure_profile = _security_profile(insecure_code)
    secure_groups = set(secure_profile["groups"])
    insecure_groups = set(insecure_profile["groups"])
    secure_tokens = set(secure_profile["tokens"])
    insecure_tokens = set(insecure_profile["tokens"])
    return {
        "secure_groups": sorted(secure_groups),
        "insecure_groups": sorted(insecure_groups),
        "shared_security_groups": sorted(secure_groups & insecure_groups),
        "secure_only_groups": sorted(secure_groups - insecure_groups),
        "insecure_only_groups": sorted(insecure_groups - secure_groups),
        "secure_only_tokens": sorted(secure_tokens - insecure_tokens),
        "insecure_only_tokens": sorted(insecure_tokens - secure_tokens),
    }


def _risk_notes_from_delta(delta: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if delta["secure_only_groups"]:
        notes.append("Secure contains protection-shaped groups that Insecure does not; preserve this contrast.")
    if delta["insecure_only_groups"]:
        notes.append("Insecure contains behavior-shaped groups absent from Secure; do not remove them during insecure repair.")
    if not delta["secure_only_groups"] and not delta["insecure_only_groups"]:
        notes.append("Python secure/insecure security shape is weakly separated; use paired oracle feedback.")
    if "validation" in delta["secure_only_groups"]:
        notes.append("Secure appears to rely on validation/sanitization; Insecure repair must not add this guard.")
    if "command" in delta["shared_security_groups"]:
        notes.append("Both versions involve command execution; preserve safe vs unsafe command handling.")
    return notes


def extract_security_delta_ir(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record.get("ID"))
    python_delta = _contrastive_delta(
        str(record.get("Secure Code", "")),
        str(record.get("Insecure Code", "")),
    )
    target_delta: dict[str, Any] = {}
    for language, secure_field, insecure_field in (
        ("cpp", "Secure Code C++", "Insecure Code C++"),
        ("go", "Secure Code Go", "Insecure Code Go"),
    ):
        delta = _contrastive_delta(
            str(record.get(secure_field, "")),
            str(record.get(insecure_field, "")),
        )
        target_delta[language] = {
            **delta,
            "diff_preserved": _diff_preserved_for_language(record, language),
        }
    return {
        "ID": record_id,
        "cwe": _extract_cwe(record_id),
        "python_delta": python_delta,
        "target_language_delta": target_delta,
        "risk_notes": _risk_notes_from_delta(python_delta),
    }


def extract_security_delta_irs(records: list[dict[str, Any]]) -> dict[str, Any]:
    items = [extract_security_delta_ir(record) for record in records]
    return {
        "records": len(items),
        "items": items,
    }


def _load_records(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_diagnostics(record_paths: dict[str, Path], output_path: Path) -> dict[str, Any]:
    architecture_records = {arch: _load_records(path) for arch, path in record_paths.items()}
    router_report = compute_oracle_router(architecture_records)
    track_router = simulate_track_router(architecture_records)
    router_regret = compute_router_regret(architecture_records, router_report)
    track_reports = {
        arch: analyze_track_outcomes(records)
        for arch, records in architecture_records.items()
    }
    failure_reports = {
        arch: analyze_failure_atlas(records)
        for arch, records in architecture_records.items()
    }
    repair_policies = {
        arch: synthesize_repair_policy(failure_report)
        for arch, failure_report in failure_reports.items()
    }
    paired_reports = {
        arch: analyze_paired_outcomes(records)
        for arch, records in architecture_records.items()
    }
    delta_ir_reports = {
        arch: extract_security_delta_irs(records)
        for arch, records in architecture_records.items()
    }
    action_plans = {
        arch: plan_paired_repair_actions(paired_reports[arch], delta_ir_reports[arch])
        for arch in architecture_records
    }
    diff_reports = {
        arch: analyze_diff_preservation(records)
        for arch, records in architecture_records.items()
    }
    report = {
        "architectures": sorted(record_paths),
        "oracle_router": router_report,
        "track_router": track_router,
        "router_regret": router_regret,
        "track_outcomes": track_reports,
        "failure_atlas": failure_reports,
        "repair_policy": repair_policies,
        "paired_outcomes": paired_reports,
        "security_delta_ir": delta_ir_reports,
        "paired_repair_actions": action_plans,
        "diff_preservation": diff_reports,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline research diagnostics over architecture record files.")
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument(
        "--records",
        action="append",
        required=True,
        help="Architecture record mapping in the form NAME=path/to/records.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    record_paths: dict[str, Path] = {}
    for item in args.records:
        if "=" not in item:
            raise ValueError(f"Expected NAME=PATH for --records, got {item}")
        name, path = item.split("=", 1)
        record_paths[name] = Path(path)
    report = run_diagnostics(record_paths, args.output_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
