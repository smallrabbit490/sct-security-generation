from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import ValidationResult, truncate_text
from .paths import ensure_work_dirs
from .validators import _docker_mount_path, _task_temp_dir, classify_validation_result, find_command, run_command_limited


PYTHON_DOCKER_IMAGE = os.environ.get("SAFECODER_PYTHON_DOCKER_IMAGE", "porta-bench-runtime-python3:latest")
PYTHON_DOCKER_ENTRYPOINT = os.environ.get("SAFECODER_PYTHON_DOCKER_ENTRYPOINT", "")
MAX_VALIDATOR_OUTPUT_CHARS = int(os.environ.get("SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS", "2000"))

_DEF_CHECK = re.compile(r"^\s*def\s+check\s*\(")
_SEC_PROBE = re.compile(r"assert_raises\s*\(\s*candidate")
_FUNC_ASSERT = re.compile(r"assert\s+candidate")


def _base_indent(lines: list[str], def_index: int) -> str:
    for line in lines[def_index + 1 :]:
        if line.strip():
            return line[: len(line) - len(line.lstrip())]
    return "    "


def _filter_combined_test(test_code: str, keep: str) -> str:
    lines = test_code.splitlines()
    def_index = next((index for index, line in enumerate(lines) if _DEF_CHECK.match(line)), None)
    if def_index is None:
        return test_code

    base = _base_indent(lines, def_index)
    output = lines[: def_index + 1]
    has_assert = False
    for line in lines[def_index + 1 :]:
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip())]
        body_level = len(indent) == len(base)
        if body_level and keep == "func" and _SEC_PROBE.match(stripped):
            continue
        if body_level and keep == "sec" and _FUNC_ASSERT.match(stripped) and not _SEC_PROBE.match(stripped):
            continue
        output.append(line)
        if stripped.startswith("assert"):
            has_assert = True
    if not has_assert:
        output.append(base + "pass")
    return "\n".join(output)


def get_python_suites(record: dict) -> tuple[str, str]:
    """Return functional and security check() suites for Base/Plus records."""

    is_plus = bool(record.get("update")) or str(record.get("subset", "")).lower() == "plus"
    combined = str(record.get("Test", "") or "")
    if is_plus and combined:
        return _filter_combined_test(combined, "func"), _filter_combined_test(combined, "sec")
    return str(record.get("Test-FP", "") or ""), str(record.get("Test-SP", "") or "")


def _docker_python_args(
    *,
    docker_cmd: str,
    temp_dir: Path,
    network: str | None,
    command: list[str],
) -> list[str]:
    args = [
        docker_cmd,
        "run",
        "--rm",
        "--stop-timeout",
        "1",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
    ]
    if network is not None:
        args.extend(["--network", network])
    if PYTHON_DOCKER_ENTRYPOINT != "__default__":
        args.extend(["--entrypoint", PYTHON_DOCKER_ENTRYPOINT])
    args.extend(
        [
            "-v",
            f"{_docker_mount_path(temp_dir)}:/work",
            "-w",
            "/work",
            "-e",
            "TMPDIR=/work/.tmp",
            "-e",
            "TEMP=/work/.tmp",
            "-e",
            "TMP=/work/.tmp",
            PYTHON_DOCKER_IMAGE,
            *command,
        ]
    )
    return args


def _run_command(args: list[str], cwd: Path, timeout: int, phase: str) -> ValidationResult:
    returncode, stdout, stderr, timed_out = run_command_limited(
        args,
        cwd,
        timeout=timeout,
        output_limit=MAX_VALIDATOR_OUTPUT_CHARS,
    )
    if not timed_out:
        return ValidationResult(
            ok=returncode == 0,
            language="python",
            mode="run",
            stdout=stdout,
            stderr=stderr,
            details={
                "returncode": returncode,
                "args": args,
                "phase": phase,
                "sandbox_dir": str(cwd),
                "error_type": classify_validation_result(
                    ok=returncode == 0,
                    phase=phase,
                    returncode=returncode,
                    stderr=stderr,
                ),
            },
        )
    return ValidationResult(
        ok=False,
        language="python",
        mode="run",
        stdout=stdout,
        stderr=stderr or "command timed out",
        details={
            "timeout": timeout,
            "args": args,
            "phase": phase,
            "sandbox_dir": str(cwd),
            "error_type": "timeout",
        },
    )


def _worker_source() -> str:
    return r'''
import json
import sys
import traceback


def build_namespace(solution):
    ns = {"__name__": "candidate_module", "__builtins__": __builtins__}
    exec(compile(solution, "<solution>", "exec"), ns)
    return ns


def run_check(base_ns, entry_point, test_code):
    if entry_point not in base_ns:
        return False, f"entry point '{entry_point}' not defined"
    candidate = base_ns[entry_point]
    test_ns = dict(base_ns)
    exec(compile(test_code, "<test>", "exec"), test_ns)
    if "check" not in test_ns:
        return False, "test code does not define check()"
    base_ns.update({k: v for k, v in test_ns.items() if k != "check"})
    try:
        test_ns["check"](candidate)
        return True, None
    except Exception:
        return False, traceback.format_exc().strip().splitlines()[-1]


def main():
    spec_path = sys.argv[1] if len(sys.argv) > 1 else "/work/spec.json"
    with open(spec_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    solution = spec.get("solution", "") or ""
    entry_point = spec.get("entry_point", "") or ""
    tests = spec.get("tests", {}) or {}
    result = {"compile": True, "tests": {}}
    try:
        base_ns = build_namespace(solution)
    except Exception:
        err = "solution error: " + traceback.format_exc().strip().splitlines()[-1]
        result["compile"] = False
        for name in tests:
            result["tests"][name] = {"passed": False, "error": err}
        print(json.dumps(result, ensure_ascii=False))
        return
    for name, test_code in tests.items():
        try:
            clean_ns = build_namespace(solution)
            passed, error = run_check(clean_ns, entry_point, test_code)
        except Exception:
            passed = False
            error = traceback.format_exc().strip().splitlines()[-1]
        result["tests"][name] = {"passed": passed, "error": error}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''.lstrip()


def _parse_worker_output(result: ValidationResult) -> dict:
    text = (result.stdout or "").strip()
    if not text:
        return {"compile": False, "tests": {}, "worker_error": result.stderr or "no worker output"}
    try:
        return json.loads(text.splitlines()[-1])
    except Exception as exc:
        return {"compile": False, "tests": {}, "worker_error": f"parse worker output failed: {exc}", "raw": text}


def _error_kind(error: str | None) -> str:
    if not error:
        return ""
    text = str(error).strip().splitlines()[-1]
    if ":" in text:
        return text.split(":", 1)[0].strip()
    return text.strip()


def compute_insecure_match_from_security_results(
    *,
    reference_sp_ok: bool,
    candidate_sp_ok: bool,
    reference_error: str | None,
    candidate_error: str | None,
) -> dict[str, object]:
    """Compare insecure security-test behavior against the source insecure code."""

    reference_failed = not reference_sp_ok
    candidate_failed = not candidate_sp_ok
    reference_kind = _error_kind(reference_error)
    candidate_kind = _error_kind(candidate_error)
    expected_failure_match = reference_failed and candidate_failed and (
        not reference_kind or not candidate_kind or reference_kind == candidate_kind
    )
    return {
        "insecure_behavior_match": reference_failed and candidate_failed,
        "expected_failure_match": expected_failure_match,
        "false_secure_by_security": candidate_sp_ok,
        "reference_security_passed": reference_sp_ok,
        "candidate_security_passed": candidate_sp_ok,
        "reference_error_kind": reference_kind,
        "candidate_error_kind": candidate_kind,
    }


def compute_insecure_match_from_test_results(
    *,
    reference_tests: dict[str, dict[str, object]],
    candidate_tests: dict[str, dict[str, object]],
    timed_out: bool,
) -> dict[str, object]:
    """Classify insecure behavior using any observed failure channel."""

    if timed_out:
        return {
            "insecure_behavior_match": True,
            "expected_failure_match": True,
            "false_secure": False,
            "failure_channel": "timeout",
        }

    fp_ok = bool((candidate_tests.get("fp") or {}).get("passed"))
    sp_ok = bool((candidate_tests.get("sp") or {}).get("passed"))
    false_secure = fp_ok and sp_ok

    if false_secure:
        return {
            "insecure_behavior_match": False,
            "expected_failure_match": False,
            "false_secure": True,
            "failure_channel": None,
        }

    ref_fp_ok = bool((reference_tests.get("fp") or {}).get("passed"))
    ref_sp_ok = bool((reference_tests.get("sp") or {}).get("passed"))
    channel = "security" if not sp_ok else "functional"
    ref_error = (reference_tests.get(channel == "security" and "sp" or "fp") or {}).get("error")
    cand_error = (candidate_tests.get(channel == "security" and "sp" or "fp") or {}).get("error")
    ref_kind = _error_kind(str(ref_error) if ref_error is not None else None)
    cand_kind = _error_kind(str(cand_error) if cand_error is not None else None)
    reference_also_failed = (channel == "security" and not ref_sp_ok) or (channel == "functional" and not ref_fp_ok)

    return {
        "insecure_behavior_match": True,
        "expected_failure_match": bool(reference_also_failed and (not ref_kind or not cand_kind or ref_kind == cand_kind)),
        "false_secure": False,
        "failure_channel": channel,
        "reference_error_kind": ref_kind,
        "candidate_error_kind": cand_kind,
    }


def run_python_checks_docker(
    *,
    code: str,
    entry_point: str,
    tests: dict[str, str],
    task_id: str,
    mode: str,
    timeout: int = 60,
) -> ValidationResult:
    docker_cmd = find_command("docker")
    if not docker_cmd:
        return ValidationResult(
            ok=False,
            language="python",
            mode=mode,
            stderr="docker was not found on PATH",
            details={"phase": "docker_check", "error_type": "environment_error"},
        )

    temp_dir = _task_temp_dir(task_id, "python", mode)
    (temp_dir / "check_worker.py").write_text(_worker_source(), encoding="utf-8")
    (temp_dir / "spec.json").write_text(
        json.dumps(
            {
                "solution": code,
                "entry_point": entry_point,
                "tests": tests,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    check_result = _run_command(
        [docker_cmd, "info", "--format", "{{.ServerVersion}}"],
        cwd=temp_dir,
        timeout=20,
        phase="docker_check",
    )
    if not check_result.ok:
        check_result.mode = mode
        check_result.details["error_type"] = "environment_error"
        return check_result

    run_result = _run_command(
        _docker_python_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            network="none",
            command=["python3", "/work/check_worker.py", "/work/spec.json"],
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="run",
    )
    payload = _parse_worker_output(run_result)
    run_result.mode = mode
    run_result.details["worker_result"] = payload
    return run_result


def validate_python_secure(record: dict, *, code: str | None = None, timeout: int = 60) -> ValidationResult:
    fp, sp = get_python_suites(record)
    if record.get("update") and record.get("Test"):
        fp = sp = str(record.get("Test") or "")
    result = run_python_checks_docker(
        code=code if code is not None else str(record.get("Secure Code", "") or ""),
        entry_point=str(record.get("Entry_Point", "") or ""),
        tests={"fp": fp, "sp": sp},
        task_id=str(record.get("ID", "unknown")),
        mode="secure",
        timeout=timeout,
    )
    worker = result.details.get("worker_result", {})
    tests = worker.get("tests", {}) if isinstance(worker, dict) else {}
    fp_ok = bool(tests.get("fp", {}).get("passed"))
    sp_ok = bool(tests.get("sp", {}).get("passed"))
    result.ok = result.ok and fp_ok and sp_ok
    result.details.update(
        {
            "secure_functional": fp_ok,
            "secure_security": sp_ok,
            "secure_func_sec": fp_ok and sp_ok,
            "checked": "docker-check-candidate",
        }
    )
    return result


def validate_python_insecure(record: dict, *, code: str | None = None, timeout: int = 60) -> ValidationResult:
    fp, sp = get_python_suites(record)
    candidate_code = code if code is not None else str(record.get("Insecure Code", "") or "")
    reference_result = run_python_checks_docker(
        code=str(record.get("Insecure Code", "") or ""),
        entry_point=str(record.get("Entry_Point", "") or ""),
        tests={"fp": fp, "sp": sp},
        task_id=str(record.get("ID", "unknown")),
        mode="insecure_reference",
        timeout=timeout,
    )
    result = run_python_checks_docker(
        code=candidate_code,
        entry_point=str(record.get("Entry_Point", "") or ""),
        tests={"fp": fp, "sp": sp},
        task_id=str(record.get("ID", "unknown")),
        mode="insecure",
        timeout=timeout,
    )
    worker = result.details.get("worker_result", {})
    tests = worker.get("tests", {}) if isinstance(worker, dict) else {}
    fp_ok = bool(tests.get("fp", {}).get("passed"))
    sp_ok = bool(tests.get("sp", {}).get("passed"))
    reference_worker = reference_result.details.get("worker_result", {})
    reference_tests = reference_worker.get("tests", {}) if isinstance(reference_worker, dict) else {}
    timed_out = result.details.get("error_type") == "timeout" or reference_result.details.get("error_type") == "timeout"
    behavior_comparison = compute_insecure_match_from_test_results(
        reference_tests=reference_tests,
        candidate_tests=tests,
        timed_out=timed_out,
    )
    false_secure = bool(behavior_comparison["false_secure"])
    behavior_match = bool(behavior_comparison["insecure_behavior_match"])
    result.ok = result.ok and behavior_match and not false_secure
    if timed_out and behavior_match and not false_secure:
        result.ok = True
    result.details.update(
        {
            "insecure_functional_observed": fp_ok,
            "insecure_security_passed_observed": sp_ok,
            "insecure_behavior_match": behavior_match,
            "false_secure": false_secure,
            "expected_failure_match": bool(behavior_comparison["expected_failure_match"]),
            "security_comparison": behavior_comparison,
            "checked": "docker-check-candidate",
        }
    )
    if result.ok:
        result.stdout = (result.stdout or "") + "\nINSECURE_BEHAVIOR_PRESERVED"
    return result
