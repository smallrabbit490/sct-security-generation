from __future__ import annotations

import argparse
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .code_extract import extract_code_block
from .insecure_behavior import validate_insecure_behavior
from .models import ValidationResult
from .paths import ensure_work_dirs
from .prompts import (
    build_repair_prompt,
    build_translation_prompt,
    build_validation_program_prompt,
)
from .validators import validate_cpp_program, validate_go_program
from .zhipu_client import DEFAULT_MODEL, ZhipuTranslationClient


Validator = Callable[[str, str, str], ValidationResult]
ExperienceProvider = Callable[[dict[str, Any], str, str, str], str]


TARGETS: tuple[tuple[str, str, Validator], ...] = (
    ("cpp", "C++", validate_cpp_program),
    ("go", "Go", validate_go_program),
)

TRANSLATION_DEFAULTS: dict[str, Any] = {
    "Secure Code C++": "",
    "Secure Code Go": "",
    "Insecure Code C++": "",
    "Insecure Code Go": "",
    "Secure Code C++ Test Result": {"ok": False, "pending": True},
    "Secure Code Go Test Result": {"ok": False, "pending": True},
    "Insecure Code C++ Behavior Result": {"ok": False, "pending": True},
    "Insecure Code Go Behavior Result": {"ok": False, "pending": True},
}


def log_stage(message: str) -> None:
    dirs = ensure_work_dirs()
    text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(text, flush=True)
    with (dirs["logs"] / "translation_pipeline.log").open("a", encoding="utf-8") as log_file:
        log_file.write(text + "\n")


def with_default_translation_fields(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    for key, value in TRANSLATION_DEFAULTS.items():
        out.setdefault(key, dict(value) if isinstance(value, dict) else value)
    return out


def result_to_dict(result: ValidationResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, ValidationResult):
        return asdict(result)
    return result


def insecure_result_to_dict(result: ValidationResult) -> dict[str, Any]:
    out = result_to_dict(result)
    if result.details.get("manual_required"):
        out["skipped"] = True
        out["manual_required"] = True
        out["reason"] = result.details.get(
            "reason",
            "No rule-based insecure behavior validator is available for this record.",
        )
    return out


def add_translation_fields(
    record: dict[str, Any],
    *,
    secure_cpp: str,
    secure_go: str,
    insecure_cpp: str,
    insecure_go: str,
    secure_cpp_result: dict[str, Any],
    secure_go_result: dict[str, Any],
    insecure_cpp_result: dict[str, Any],
    insecure_go_result: dict[str, Any],
) -> dict[str, Any]:
    out = dict(record)
    out["Secure Code C++"] = secure_cpp
    out["Secure Code Go"] = secure_go
    out["Insecure Code C++"] = insecure_cpp
    out["Insecure Code Go"] = insecure_go
    out["Secure Code C++ Test Result"] = secure_cpp_result
    out["Secure Code Go Test Result"] = secure_go_result
    out["Insecure Code C++ Behavior Result"] = insecure_cpp_result
    out["Insecure Code Go Behavior Result"] = insecure_go_result
    return out


def _failure_text(result: ValidationResult) -> str:
    details = json.dumps(result.details, ensure_ascii=False, indent=2)
    return f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}\n\ndetails:\n{details}"


def should_use_static_insecure_result(result: ValidationResult) -> bool:
    return (
        result.details.get("strategy") == "cwe-502-json-rejection"
        and result.details.get("checked") == "executable-harness"
    )


def _static_context_text(result: ValidationResult) -> str:
    details = json.dumps(result.details, ensure_ascii=False, indent=2)
    return (
        "Static/rule-based insecure audit context only. "
        "Do not treat this as automatic pass evidence; the translation still needs executable sandbox validation.\n"
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}\n\ndetails:\n{details}"
    )


def _validation_context_text(result: ValidationResult) -> str:
    return (
        "\n\n# Previous target validation failure:\n"
        "# The previous generated validation program failed in the target-language sandbox.\n"
        "# Avoid repeating this exact harness/code mistake in the next validation program.\n"
        f"# {_failure_text(result).replace(chr(10), chr(10) + '# ')}\n"
    )


def translate_code(
    client: ZhipuTranslationClient,
    record: dict[str, Any],
    source_field: str,
    language_label: str,
    language_code: str,
    experience_context: str = "",
) -> str:
    prompt = build_translation_prompt(
        problem=record.get("Problem", ""),
        entry_point=record.get("Entry_Point", ""),
        source_code=record.get(source_field, ""),
        source_field=source_field,
        target_language=language_label,
        experience_context=experience_context,
    )
    response = client.translate(prompt)
    return extract_code_block(response, language_code)


def validate_translation(
    client: ZhipuTranslationClient,
    record: dict[str, Any],
    source_field: str,
    translated_code: str,
    language_label: str,
    language_code: str,
    validator: Validator,
    mode: str,
    max_repair_attempts: int,
    skip_validation: bool = False,
    experience_context: str = "",
) -> tuple[str, dict[str, Any]]:
    if skip_validation:
        return translated_code, {
            "ok": False,
            "skipped": True,
            "reason": "skip-validation was enabled",
            "language": language_code,
            "mode": mode,
        }

    current_code = translated_code
    last_result = ValidationResult(
        ok=False,
        language=language_code,
        mode=mode,
        stderr="validation was not run",
    )

    for attempt in range(max_repair_attempts + 1):
        python_test = record.get("Test", "")
        if attempt > 0:
            python_test = f"{python_test}{_validation_context_text(last_result)}"
        harness_prompt = build_validation_program_prompt(
            problem=record.get("Problem", ""),
            entry_point=record.get("Entry_Point", ""),
            source_code=record.get(source_field, ""),
            translated_code=current_code,
            python_test=python_test,
            target_language=language_label,
            mode=mode,
        )
        try:
            harness_response = client.translate(harness_prompt)
            harness_code = extract_code_block(harness_response, language_code)
            last_result = validator(harness_code, str(record.get("ID", "unknown")), mode)
        except Exception as exc:
            last_result = ValidationResult(
                ok=False,
                language=language_code,
                mode=mode,
                stderr=str(exc),
                details={"attempt": attempt + 1, "stage": "validation_harness"},
            )
            return current_code, result_to_dict(last_result)
        last_result.details["attempt"] = attempt + 1

        if last_result.ok:
            return current_code, result_to_dict(last_result)

        if attempt >= max_repair_attempts:
            break

        repair_prompt = build_repair_prompt(
            problem=record.get("Problem", ""),
            entry_point=record.get("Entry_Point", ""),
            source_code=record.get(source_field, ""),
            translated_code=current_code,
            target_language=language_label,
            failure_text=_failure_text(last_result),
            mode=mode,
            experience_context=experience_context,
        )
        try:
            repair_response = client.translate(repair_prompt)
            current_code = extract_code_block(repair_response, language_code)
        except Exception as exc:
            last_result.stderr = f"{last_result.stderr}\nrepair failed: {exc}"
            last_result.details["stage"] = "repair"
            return current_code, result_to_dict(last_result)

    return current_code, result_to_dict(last_result)


def validate_insecure_translation_with_execution(
    client: ZhipuTranslationClient,
    record: dict[str, Any],
    translated_code: str,
    language_label: str,
    language_code: str,
    validator: Validator,
    max_repair_attempts: int,
    static_context: ValidationResult | None = None,
    experience_context: str = "",
) -> tuple[str, dict[str, Any]]:
    working_record = dict(record)
    if static_context is not None:
        working_record["Test"] = (
            f"{record.get('Test', '')}\n\n"
            "# Static insecure audit context from the pipeline:\n"
            f"{_static_context_text(static_context)}\n"
        )
    return validate_translation(
        client,
        working_record,
        "Insecure Code",
        translated_code,
        language_label,
        language_code,
        validator,
        "insecure",
        max_repair_attempts,
        skip_validation=False,
        experience_context=experience_context,
    )


def process_record(
    record: dict[str, Any],
    *,
    model: str,
    max_repair_attempts: int,
    skip_api: bool = False,
    skip_validation: bool = False,
    skip_secure_validation: bool = False,
    skip_insecure_validation: bool = False,
    request_timeout: int = 180,
    max_tokens: int = 65536,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    experience_provider: ExperienceProvider | None = None,
) -> dict[str, Any]:
    working_record = with_default_translation_fields(record)

    def update_field(code_key: str, result_key: str, code: str, result: dict[str, Any]) -> None:
        working_record[code_key] = code
        working_record[result_key] = result
        if on_update is not None:
            on_update(dict(working_record))

    if skip_api:
        skipped = {"ok": False, "skipped": True, "reason": "skip-api was enabled"}
        update_field("Secure Code C++", "Secure Code C++ Test Result", "", skipped)
        update_field("Secure Code Go", "Secure Code Go Test Result", "", skipped)
        update_field("Insecure Code C++", "Insecure Code C++ Behavior Result", "", skipped)
        update_field("Insecure Code Go", "Insecure Code Go Behavior Result", "", skipped)
        return working_record

    client = ZhipuTranslationClient(model=model, request_timeout=request_timeout, max_tokens=max_tokens)
    translations: dict[str, str] = {}
    results: dict[str, dict[str, Any]] = {}
    record_id = str(record.get("ID", "unknown"))

    for language_code, language_label, validator in TARGETS:
        secure_key = f"secure_{language_code}"
        insecure_key = f"insecure_{language_code}"

        try:
            log_stage(f"{record_id}: translating Secure Code to {language_label}")
            secure_translation_experience = (
                experience_provider(record, language_code, "secure", "translation")
                if experience_provider is not None
                else ""
            )
            secure_repair_experience = (
                experience_provider(record, language_code, "secure", "repair")
                if experience_provider is not None
                else ""
            )
            secure_code = translate_code(
                client,
                record,
                "Secure Code",
                language_label,
                language_code,
                experience_context=secure_translation_experience,
            )
            if not (skip_validation or skip_secure_validation):
                log_stage(f"{record_id}: validating Secure Code {language_label}")
            secure_code, secure_result = validate_translation(
                client,
                record,
                "Secure Code",
                secure_code,
                language_label,
                language_code,
                validator,
                "secure",
                max_repair_attempts,
                skip_validation=skip_validation or skip_secure_validation,
                experience_context=secure_repair_experience,
            )
        except Exception as exc:
            secure_code = ""
            secure_result = {
                "ok": False,
                "language": language_code,
                "mode": "secure",
                "error": str(exc),
            }
        translations[secure_key] = secure_code
        results[secure_key] = secure_result
        if language_code == "cpp":
            update_field("Secure Code C++", "Secure Code C++ Test Result", secure_code, secure_result)
        else:
            update_field("Secure Code Go", "Secure Code Go Test Result", secure_code, secure_result)

        try:
            log_stage(f"{record_id}: translating Insecure Code to {language_label}")
            insecure_translation_experience = (
                experience_provider(record, language_code, "insecure", "translation")
                if experience_provider is not None
                else ""
            )
            insecure_repair_experience = (
                experience_provider(record, language_code, "insecure", "repair")
                if experience_provider is not None
                else ""
            )
            insecure_code = translate_code(
                client,
                record,
                "Insecure Code",
                language_label,
                language_code,
                experience_context=insecure_translation_experience,
            )
            if skip_validation or skip_insecure_validation:
                insecure_result = {
                    "ok": False,
                    "skipped": True,
                    "reason": "skip-validation was enabled" if skip_validation else "skip-insecure-validation was enabled",
                    "language": language_code,
                    "mode": "insecure",
                }
            else:
                log_stage(f"{record_id}: validating Insecure Code {language_label}")
                automated_result = validate_insecure_behavior(record, insecure_code, language_code)
                if should_use_static_insecure_result(automated_result):
                    insecure_result = insecure_result_to_dict(automated_result)
                else:
                    insecure_code, insecure_result = validate_insecure_translation_with_execution(
                        client,
                        record,
                        insecure_code,
                        language_label,
                        language_code,
                        validator,
                        max_repair_attempts,
                        static_context=automated_result,
                        experience_context=insecure_repair_experience,
                    )
        except Exception as exc:
            insecure_code = ""
            insecure_result = {
                "ok": False,
                "language": language_code,
                "mode": "insecure",
                "error": str(exc),
            }
        translations[insecure_key] = insecure_code
        results[insecure_key] = insecure_result
        if language_code == "cpp":
            update_field("Insecure Code C++", "Insecure Code C++ Behavior Result", insecure_code, insecure_result)
        else:
            update_field("Insecure Code Go", "Insecure Code Go Behavior Result", insecure_code, insecure_result)

    return add_translation_fields(
        record,
        secure_cpp=translations["secure_cpp"],
        secure_go=translations["secure_go"],
        insecure_cpp=translations["insecure_cpp"],
        insecure_go=translations["insecure_go"],
        secure_cpp_result=results["secure_cpp"],
        secure_go_result=results["secure_go"],
        insecure_cpp_result=results["insecure_cpp"],
        insecure_go_result=results["insecure_go"],
    )


def _skipped_result(language_code: str, mode: str, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "skipped": True,
        "reason": reason,
        "language": language_code,
        "mode": mode,
    }


def _missing_result(language_code: str, mode: str, field_name: str) -> dict[str, Any]:
    return {
        "ok": False,
        "language": language_code,
        "mode": mode,
        "error": f"Missing translated field: {field_name}",
    }


def _result_ok(record: dict[str, Any], result_key: str) -> bool:
    result = record.get(result_key)
    return isinstance(result, dict) and result.get("ok") is True


def _timeout_result(language_code: str, mode: str, timeout_seconds: int, stage: str) -> dict[str, Any]:
    return {
        "ok": False,
        "language": language_code,
        "mode": mode,
        "stderr": f"record validation timed out after {timeout_seconds} seconds",
        "details": {
            "phase": stage,
            "error_type": "timeout",
            "timeout": timeout_seconds,
        },
    }


def mark_record_timeout(
    record: dict[str, Any],
    *,
    timeout_seconds: int,
    skip_secure_validation: bool,
    skip_insecure_validation: bool,
) -> dict[str, Any]:
    out = with_default_translation_fields(record)
    if not skip_secure_validation:
        out["Secure Code C++ Test Result"] = _timeout_result("cpp", "secure", timeout_seconds, "record_timeout")
        out["Secure Code Go Test Result"] = _timeout_result("go", "secure", timeout_seconds, "record_timeout")
    if not skip_insecure_validation:
        out["Insecure Code C++ Behavior Result"] = _timeout_result("cpp", "insecure", timeout_seconds, "record_timeout")
        out["Insecure Code Go Behavior Result"] = _timeout_result("go", "insecure", timeout_seconds, "record_timeout")
    out["Translation Pipeline Error"] = f"record timed out after {timeout_seconds} seconds"
    return out


def validate_existing_record(
    record: dict[str, Any],
    *,
    model: str,
    max_repair_attempts: int,
    skip_validation: bool,
    skip_secure_validation: bool,
    skip_insecure_validation: bool,
    request_timeout: int,
    max_tokens: int = 65536,
    on_update: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    working_record = with_default_translation_fields(record)
    client = ZhipuTranslationClient(model=model, request_timeout=request_timeout, max_tokens=max_tokens)
    record_id = str(record.get("ID", "unknown"))

    def update(result_key: str, result: dict[str, Any]) -> None:
        working_record[result_key] = result
        if on_update is not None:
            on_update(dict(working_record))

    for language_code, language_label, validator in TARGETS:
        if language_code == "cpp":
            secure_code_key = "Secure Code C++"
            secure_result_key = "Secure Code C++ Test Result"
            insecure_code_key = "Insecure Code C++"
            insecure_result_key = "Insecure Code C++ Behavior Result"
        else:
            secure_code_key = "Secure Code Go"
            secure_result_key = "Secure Code Go Test Result"
            insecure_code_key = "Insecure Code Go"
            insecure_result_key = "Insecure Code Go Behavior Result"

        secure_code = str(working_record.get(secure_code_key, ""))
        if _result_ok(working_record, secure_result_key):
            pass
        elif not secure_code:
            update(secure_result_key, _missing_result(language_code, "secure", secure_code_key))
        elif skip_validation or skip_secure_validation:
            update(
                secure_result_key,
                _skipped_result(
                    language_code,
                    "secure",
                    "skip-validation was enabled" if skip_validation else "skip-secure-validation was enabled",
                ),
            )
        else:
            log_stage(f"{record_id}: validating existing Secure Code {language_label}")
            repaired_secure_code, secure_result = validate_translation(
                client,
                working_record,
                "Secure Code",
                secure_code,
                language_label,
                language_code,
                validator,
                "secure",
                max_repair_attempts,
            )
            working_record[secure_code_key] = repaired_secure_code
            update(secure_result_key, secure_result)

        insecure_code = str(working_record.get(insecure_code_key, ""))
        if _result_ok(working_record, insecure_result_key):
            pass
        elif not insecure_code:
            update(insecure_result_key, _missing_result(language_code, "insecure", insecure_code_key))
        elif skip_validation or skip_insecure_validation:
            update(
                insecure_result_key,
                _skipped_result(
                    language_code,
                    "insecure",
                    "skip-validation was enabled" if skip_validation else "skip-insecure-validation was enabled",
                ),
            )
        else:
            log_stage(f"{record_id}: validating existing Insecure Code {language_label}")
            automated_result = validate_insecure_behavior(working_record, insecure_code, language_code)
            if should_use_static_insecure_result(automated_result):
                update(insecure_result_key, insecure_result_to_dict(automated_result))
            else:
                repaired_insecure_code, insecure_result = validate_insecure_translation_with_execution(
                    client,
                    working_record,
                    insecure_code,
                    language_label,
                    language_code,
                    validator,
                    max_repair_attempts,
                    static_context=automated_result,
                )
                working_record[insecure_code_key] = repaired_insecure_code
                update(insecure_result_key, insecure_result)

    return working_record


def summarize_records(records: list[dict[str, Any]]) -> dict[str, int]:
    def ok_count(field: str) -> int:
        return sum(1 for record in records if record.get(field, {}).get("ok") is True)

    def skipped_count(field: str) -> int:
        return sum(1 for record in records if record.get(field, {}).get("skipped") is True)

    return {
        "records": len(records),
        "secure_cpp_ok": ok_count("Secure Code C++ Test Result"),
        "secure_go_ok": ok_count("Secure Code Go Test Result"),
        "insecure_cpp_ok": ok_count("Insecure Code C++ Behavior Result"),
        "insecure_go_ok": ok_count("Insecure Code Go Behavior Result"),
        "secure_cpp_skipped": skipped_count("Secure Code C++ Test Result"),
        "secure_go_skipped": skipped_count("Secure Code Go Test Result"),
        "insecure_cpp_skipped": skipped_count("Insecure Code C++ Behavior Result"),
        "insecure_go_skipped": skipped_count("Insecure Code Go Behavior Result"),
    }


def write_summary(output_path: Path, records: list[dict[str, Any]]) -> None:
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(summarize_records(records), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_existing_by_id(output_path: Path) -> dict[str, dict[str, Any]]:
    if not output_path.exists():
        return {}
    records = json.loads(output_path.read_text(encoding="utf-8"))
    return {str(record.get("ID")): record for record in records}


def is_translation_complete(record: dict[str, Any]) -> bool:
    return all(
        bool(record.get(field))
        for field in (
            "Secure Code C++",
            "Secure Code Go",
            "Insecure Code C++",
            "Insecure Code Go",
        )
    )


def is_validation_complete(record: dict[str, Any], *, skip_secure: bool, skip_insecure: bool) -> bool:
    result_fields: list[tuple[str, bool]] = []
    if not skip_secure:
        result_fields.extend([
            ("Secure Code C++ Test Result", False),
            ("Secure Code Go Test Result", False),
        ])
    if not skip_insecure:
        result_fields.extend([
            ("Insecure Code C++ Behavior Result", True),
            ("Insecure Code Go Behavior Result", True),
        ])
    if not result_fields:
        return True
    for field, is_insecure_field in result_fields:
        result = record.get(field)
        if not isinstance(result, dict):
            return False
        if result.get("pending") is True:
            return False
        if result.get("ok") is True:
            continue
        if result.get("skipped") is True:
            return False
        else:
            return False
    return True


def safe_write_json(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def run_dataset(
    data_path: Path,
    output_path: Path,
    model: str,
    max_workers: int,
    limit: int | None,
    resume: bool,
    max_repair_attempts: int,
    skip_api: bool,
    skip_validation: bool,
    skip_secure_validation: bool,
    skip_insecure_validation: bool,
    request_timeout: int,
    max_tokens: int,
    validate_existing: bool = False,
) -> list[dict[str, Any]]:
    ensure_work_dirs()
    records = json.loads(data_path.read_text(encoding="utf-8"))
    if limit is not None:
        records = records[:limit]

    if validate_existing:
        output_by_id: dict[str, dict[str, Any]] = load_existing_by_id(output_path) if resume else {}

        def persist_existing(updated_record: dict[str, Any]) -> None:
            output_by_id[str(updated_record.get("ID"))] = updated_record
            merged = []
            for original in records:
                record_id = str(original.get("ID"))
                merged.append(output_by_id.get(record_id, with_default_translation_fields(original)))
            safe_write_json(output_path, merged)

        validated_records: list[dict[str, Any]] = []
        pending_existing: list[dict[str, Any]] = []
        for record in records:
            record_id = str(record.get("ID"))
            existing_record = output_by_id.get(record_id)
            if (
                resume
                and existing_record is not None
                and is_validation_complete(
                    existing_record,
                    skip_secure=skip_validation or skip_secure_validation,
                    skip_insecure=skip_validation or skip_insecure_validation,
                )
            ):
                log_stage(f"{record_id}: validation already complete, skipping because resume is enabled")
                validated_records.append(existing_record)
                continue
            current = with_default_translation_fields(existing_record or record)
            pending_existing.append(current)
            persist_existing(current)

        if max_workers <= 1:
            for current in pending_existing:
                record_id = str(current.get("ID"))
                log_stage(f"{record_id}: validating existing translated record")
                validated = validate_existing_record(
                    current,
                    model=model,
                    max_repair_attempts=max_repair_attempts,
                    skip_validation=skip_validation,
                    skip_secure_validation=skip_secure_validation,
                    skip_insecure_validation=skip_insecure_validation,
                    request_timeout=request_timeout,
                    max_tokens=max_tokens,
                    on_update=persist_existing,
                )
                validated_records.append(validated)
                persist_existing(validated)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for current in pending_existing:
                    log_stage(f"{current.get('ID')}: validating existing translated record")
                futures = {
                    executor.submit(
                        validate_existing_record,
                        current,
                        model=model,
                        max_repair_attempts=max_repair_attempts,
                        skip_validation=skip_validation,
                        skip_secure_validation=skip_secure_validation,
                        skip_insecure_validation=skip_insecure_validation,
                        request_timeout=request_timeout,
                        max_tokens=max_tokens,
                    ): current
                    for current in pending_existing
                }
                for future in as_completed(futures):
                    current = futures[future]
                    record_id = str(current.get("ID"))
                    try:
                        validated = future.result()
                    except Exception as exc:
                        validated = dict(current)
                        validated["Translation Pipeline Error"] = str(exc)
                    validated_records.append(validated)
                    output_by_id[record_id] = validated
                    persist_existing(validated)
        final_validated_records = [
            output_by_id.get(str(record.get("ID")), with_default_translation_fields(record))
            for record in records
        ]
        safe_write_json(output_path, final_validated_records)
        write_summary(output_path, final_validated_records)
        return final_validated_records

    existing = load_existing_by_id(output_path) if resume else {}
    output: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for record in records:
        record_id = str(record.get("ID"))
        if record_id in existing and is_translation_complete(existing[record_id]):
            output.append(existing[record_id])
        else:
            pending.append(record)

    output_by_id: dict[str, dict[str, Any]] = {str(record.get("ID")): record for record in output}

    def persist_update(updated_record: dict[str, Any]) -> None:
        output_by_id[str(updated_record.get("ID"))] = updated_record
        merged = []
        for original in records:
            record_id = str(original.get("ID"))
            merged.append(output_by_id.get(record_id, with_default_translation_fields(original)))
        safe_write_json(output_path, merged)

    if pending:
        if max_workers <= 1:
            for record in pending:
                record_id = str(record.get("ID"))
                log_stage(f"{record_id}: starting record")
                current = with_default_translation_fields(record)
                persist_update(current)
                completed = process_record(
                    record,
                    model=model,
                    max_repair_attempts=max_repair_attempts,
                    skip_api=skip_api,
                    skip_validation=skip_validation,
                    skip_secure_validation=skip_secure_validation,
                    skip_insecure_validation=skip_insecure_validation,
                    request_timeout=request_timeout,
                    max_tokens=max_tokens,
                    on_update=persist_update,
                )
                output_by_id[record_id] = completed
                persist_update(completed)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        process_record,
                        record,
                        model=model,
                        max_repair_attempts=max_repair_attempts,
                        skip_api=skip_api,
                        skip_validation=skip_validation,
                        skip_secure_validation=skip_secure_validation,
                        skip_insecure_validation=skip_insecure_validation,
                        request_timeout=request_timeout,
                        max_tokens=max_tokens,
                    ): record
                    for record in pending
                }
                completed_by_id: dict[str, dict[str, Any]] = {}
                for future in as_completed(futures):
                    record = futures[future]
                    try:
                        completed_by_id[str(record.get("ID"))] = future.result()
                    except Exception as exc:
                        failed = dict(record)
                        failed["Translation Pipeline Error"] = str(exc)
                        completed_by_id[str(record.get("ID"))] = failed
                    completed = completed_by_id[str(record.get("ID"))]
                    output_by_id[str(record.get("ID"))] = completed
                    persist_update(completed)

            for record in pending:
                if str(record.get("ID")) not in output_by_id:
                    completed = completed_by_id[str(record.get("ID"))]
                    output_by_id[str(record.get("ID"))] = completed
                    persist_update(completed)

    final_output = []
    for record in records:
        record_id = str(record.get("ID"))
        final_output.append(output_by_id.get(record_id, with_default_translation_fields(record)))
    safe_write_json(output_path, final_output)
    write_summary(output_path, final_output)
    return final_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate CodeSecEval Python records to C++ and Go.")
    parser.add_argument("--data-path", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-repair-attempts", type=int, default=2)
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-secure-validation", action="store_true")
    parser.add_argument("--skip-insecure-validation", action="store_true")
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--validate-existing", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = run_dataset(
        data_path=args.data_path,
        output_path=args.output_path,
        model=args.model,
        max_workers=args.max_workers,
        limit=args.limit,
        resume=args.resume,
        max_repair_attempts=args.max_repair_attempts,
        skip_api=args.skip_api,
        skip_validation=args.skip_validation,
        skip_secure_validation=args.skip_secure_validation,
        skip_insecure_validation=args.skip_insecure_validation,
        request_timeout=args.request_timeout,
        max_tokens=args.max_tokens,
        validate_existing=args.validate_existing,
    )
    print(f"Wrote {len(records)} records to {args.output_path}")


if __name__ == "__main__":
    main()
