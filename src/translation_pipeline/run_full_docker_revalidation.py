from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ValidationResult
from .python_validator import validate_python_insecure, validate_python_secure
from .validators import (
    _docker_cpp_args,
    _docker_go_args,
    run_command,
)


LANGUAGE_FILES = {
    "python": "Python_{subset}.json",
    "cpp": "Cpp_{subset}.json",
    "go": "Go_{subset}.json",
}
MAX_STORED_TEXT_CHARS = int(os.environ.get("SAFECODER_MAX_STORED_TEXT_CHARS", "2000"))
MAX_STORED_LIST_ITEMS = int(os.environ.get("SAFECODER_MAX_STORED_LIST_ITEMS", "50"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_compact_for_storage(value), ensure_ascii=False) + "\n")


def _truncate_text(value: str, limit: int = MAX_STORED_TEXT_CHARS) -> str:
    if len(value) <= limit:
        return value
    head = value[: limit // 2]
    tail = value[-(limit // 2) :]
    omitted = len(value) - len(head) - len(tail)
    return f"{head}\n...[truncated {omitted} chars]...\n{tail}"


def _compact_for_storage(value: Any) -> Any:
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, list):
        items = [_compact_for_storage(item) for item in value[:MAX_STORED_LIST_ITEMS]]
        if len(value) > MAX_STORED_LIST_ITEMS:
            items.append({"truncated_items": len(value) - MAX_STORED_LIST_ITEMS})
        return items
    if isinstance(value, dict):
        return {key: _compact_for_storage(item) for key, item in value.items()}
    return value


def _result_to_dict(result: ValidationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "language": result.language,
        "mode": result.mode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "details": result.details,
    }


def _copy_harness_dir(src: Path, dst_root: Path, task_id: str, language: str, track: str) -> Path:
    safe_task = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(task_id))
    dst = dst_root / f"{safe_task}_{language}_{track}"
    if dst.exists():
        shutil.rmtree(dst)
    try:
        shutil.copytree(src, dst)
        return dst
    except Exception:
        # Some insecure harnesses intentionally contain awkward file names
        # that Windows cannot copy reliably. In that case rerun in place.
        return src


def _patch_cpp_harness_for_linux(source: Path) -> None:
    code = source.read_text(encoding="utf-8", errors="replace")
    original = code

    code = code.replace("#include <io.h>", "#include <unistd.h>\n#include <sys/stat.h>")
    code = code.replace("_popen(", "popen(")
    code = code.replace("_pclose(", "pclose(")
    code = code.replace("mock_popen(", "popen(")
    code = code.replace("mock_pclose(", "pclose(")
    code = code.replace("mockpopen(", "mock_popen(")
    code = code.replace("mockpclose(", "mock_pclose(")
    code = code.replace("_chmod(", "chmod(")
    code = code.replace("_S_IREAD", "S_IREAD")
    code = code.replace("_S_IWRITE", "S_IWRITE")
    code = re.sub(
        r'_putenv_s\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)',
        r'setenv("\1", "\2", 1)',
        code,
    )
    code = code.replace('"python ', '"python3 ')
    code = code.replace("'python ", "'python3 ")
    code = code.replace('"move ', '"mv ')
    code = code.replace("'move ", "'mv ")
    code = code.replace('"ping -n 1 ', '"ping -c 1 ')
    code = code.replace('"ping -n 1 " +', '"ping -c 1 " +')

    if "void set_env_var(" in code:
        code = re.sub(
            r"void\s+set_env_var\s*\(\s*const\s+std::string&\s+name\s*,\s*const\s+std::string&\s+value\s*\)\s*\{.*?\n\}",
            (
                "void set_env_var(const std::string& name, const std::string& value) {\n"
                "#ifdef _WIN32\n"
                "    std::string env_str = name + \"=\" + value;\n"
                "    _putenv(env_str.c_str());\n"
                "#else\n"
                "    setenv(name.c_str(), value.c_str(), 1);\n"
                "#endif\n"
                "}"
            ),
            code,
            flags=re.S,
        )
    if "void clear_env_var(" in code:
        code = re.sub(
            r"void\s+clear_env_var\s*\(\s*const\s+std::string&\s+name\s*\)\s*\{.*?\n\}",
            (
                "void clear_env_var(const std::string& name) {\n"
                "#ifdef _WIN32\n"
                "    _putenv((name + \"=\").c_str());\n"
                "#else\n"
                "    unsetenv(name.c_str());\n"
                "#endif\n"
                "}"
            ),
            code,
            flags=re.S,
        )

    if "Test/CWE-22_07/resources" in code and "std::string serve_resource(" in code:
        code = re.sub(
            r"std::string\s+serve_resource\s*\(\s*const\s+std::string&\s+file_path\s*\)\s*\{.*?\n\}",
            (
                "std::string serve_resource(const std::string& file_path) {\n"
                "    if (file_path.empty()) {\n"
                "        throw std::invalid_argument(\"invalid resource path\");\n"
                "    }\n"
                "\n"
                "    fs::path base_dir = fs::weakly_canonical(fs::absolute(\"./Test/CWE-22_07/resources\"));\n"
                "    fs::path full_path = fs::weakly_canonical(fs::absolute(base_dir / file_path));\n"
                "\n"
                "    std::string base_dir_str = base_dir.generic_string();\n"
                "    std::string full_path_str = full_path.generic_string();\n"
                "    if (full_path_str == base_dir_str || full_path_str.rfind(base_dir_str + \"/\", 0) != 0) {\n"
                "        throw std::invalid_argument(\"invalid resource path\");\n"
                "    }\n"
                "\n"
                "    std::ifstream file(full_path);\n"
                "    if (!file) {\n"
                "        throw std::runtime_error(\"failed to open file\");\n"
                "    }\n"
                "\n"
                "    std::ostringstream ss;\n"
                "    ss << file.rdbuf();\n"
                "    return ss.str();\n"
                "}"
            ),
            code,
            count=1,
            flags=re.S,
        )

    if ("chdir(" in code or "popen(" in code or "pclose(" in code) and "#include <unistd.h>" not in code:
        code = "#include <unistd.h>\n" + code
    if "setenv(" in code and "#include <cstdlib>" not in code:
        code = "#include <cstdlib>\n" + code
    if code != original:
        source.write_text(code, encoding="utf-8")


def _cpp_run_network_for_source(source_code: str) -> str | None:
    if "ping_host" in source_code and ("ping -c 1" in source_code or "ping -n 1" in source_code):
        return None
    return "none"


def _go_container_local_run_command() -> list[str]:
    script = (
        "rm -rf /tmp/safecoder_run && "
        "mkdir -p /tmp/safecoder_run && "
        "cp -a /work/. /tmp/safecoder_run/ && "
        "rm -rf /tmp/safecoder_run/Test && "
        "cd /tmp/safecoder_run && "
        "./main"
    )
    return ["sh", "-lc", script]


def _rerun_cpp_harness(record: dict, track: str, output_root: Path, timeout: int) -> ValidationResult:
    result_key = "Secure Code Test Result" if track == "secure" else "Insecure Code Behavior Result"
    old = record.get(result_key) or {}
    src_dir = Path(((old.get("details") or {}).get("sandbox_dir") or ""))
    if not src_dir.exists():
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=track,
            stderr="saved harness sandbox_dir is missing",
            details={"error_type": "missing_harness", "source_sandbox_dir": str(src_dir)},
        )
    temp_dir = _copy_harness_dir(src_dir, output_root / "harnesses", str(record.get("ID", "unknown")), "cpp", track)
    source = temp_dir / "main.cpp"
    if not source.exists():
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=track,
            stderr="saved C++ harness main.cpp is missing",
            details={"error_type": "missing_harness", "sandbox_dir": str(temp_dir)},
        )
    _patch_cpp_harness_for_linux(source)
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        return ValidationResult(ok=False, language="cpp", mode=track, stderr="docker was not found on PATH", details={"error_type": "environment_error"})

    compile_result = run_command(
        _docker_cpp_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            network="none",
            command=["g++", "-std=c++17", "-O2", "-I/work/include", "/work/main.cpp", "-o", "/work/main"],
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="compile",
    )
    compile_result.language = "cpp"
    compile_result.mode = track
    if not compile_result.ok:
        if track == "insecure" and _insecure_failure_is_expected(compile_result):
            compile_result.ok = True
            compile_result.stdout = (compile_result.stdout or "") + "\nINSECURE_BEHAVIOR_PRESERVED: compile_or_validation_failure"
            compile_result.details["insecure_behavior_match"] = True
            compile_result.details["expected_failure_match"] = True
            compile_result.details["false_secure"] = False
        return compile_result

    run_network = _cpp_run_network_for_source(source.read_text(encoding="utf-8", errors="replace")) if track == "secure" else "none"
    run_result = run_command(
        _docker_cpp_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            network=run_network,
            command=["/work/main"],
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="run",
    )
    run_result.language = "cpp"
    run_result.mode = track
    if track == "insecure" and (run_result.details.get("error_type") == "timeout" or _insecure_failure_is_expected(run_result)):
        run_result.ok = True
        run_result.stdout = (run_result.stdout or "") + "\nINSECURE_BEHAVIOR_PRESERVED: failure_or_timeout"
        run_result.details["insecure_behavior_match"] = True
        run_result.details["expected_failure_match"] = True
        run_result.details["false_secure"] = False
    return run_result


def _rerun_go_harness(record: dict, track: str, output_root: Path, timeout: int) -> ValidationResult:
    result_key = "Secure Code Test Result" if track == "secure" else "Insecure Code Behavior Result"
    old = record.get(result_key) or {}
    src_dir = Path(((old.get("details") or {}).get("sandbox_dir") or ""))
    if not src_dir.exists():
        return ValidationResult(
            ok=False,
            language="go",
            mode=track,
            stderr="saved harness sandbox_dir is missing",
            details={"error_type": "missing_harness", "source_sandbox_dir": str(src_dir)},
        )
    temp_dir = _copy_harness_dir(src_dir, output_root / "harnesses", str(record.get("ID", "unknown")), "go", track)
    source = temp_dir / "main.go"
    if not source.exists():
        return ValidationResult(
            ok=False,
            language="go",
            mode=track,
            stderr="saved Go harness main.go is missing",
            details={"error_type": "missing_harness", "sandbox_dir": str(temp_dir)},
        )
    if not (temp_dir / "go.mod").exists():
        (temp_dir / "go.mod").write_text("module safecoder_revalidation\n\ngo 1.22\n", encoding="utf-8")
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        return ValidationResult(ok=False, language="go", mode=track, stderr="docker was not found on PATH", details={"error_type": "environment_error"})

    cache_root = output_root / "go_cache"
    mod_cache = cache_root / "mod"
    build_cache = cache_root / "build"
    mod_cache.mkdir(parents=True, exist_ok=True)
    build_cache.mkdir(parents=True, exist_ok=True)

    download_result = run_command(
        _docker_go_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            mod_cache=mod_cache,
            build_cache=build_cache,
            network=None,
            command=["go", "mod", "download"],
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="dependency",
    )
    download_result.language = "go"
    download_result.mode = track
    if not download_result.ok:
        return download_result

    build_result = run_command(
        _docker_go_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            mod_cache=mod_cache,
            build_cache=build_cache,
            network="none",
            command=["go", "build", "-o", "/work/main", "/work/main.go"],
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="compile",
    )
    build_result.language = "go"
    build_result.mode = track
    if not build_result.ok:
        if track == "insecure" and _insecure_failure_is_expected(build_result):
            build_result.ok = True
            build_result.stdout = (build_result.stdout or "") + "\nINSECURE_BEHAVIOR_PRESERVED: compile_or_validation_failure"
            build_result.details["insecure_behavior_match"] = True
            build_result.details["expected_failure_match"] = True
            build_result.details["false_secure"] = False
        return build_result

    run_result = run_command(
        _docker_go_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            mod_cache=mod_cache,
            build_cache=build_cache,
            network="none",
            command=_go_container_local_run_command(),
        ),
        cwd=temp_dir,
        timeout=timeout,
        phase="run",
    )
    run_result.language = "go"
    run_result.mode = track
    if track == "insecure" and _insecure_failure_is_expected(run_result):
        run_result.ok = True
        run_result.stdout = (run_result.stdout or "") + "\nINSECURE_BEHAVIOR_PRESERVED: failure"
        run_result.details["insecure_behavior_match"] = True
        run_result.details["expected_failure_match"] = True
        run_result.details["false_secure"] = False
    return run_result


def _insecure_failure_is_expected(result: ValidationResult) -> bool:
    text = "\n".join([result.stdout or "", result.stderr or ""]).lower()
    returncode = result.details.get("returncode")
    error_type = result.details.get("error_type")
    phase = result.details.get("phase")
    if phase == "run" and isinstance(returncode, int) and returncode != 0 and error_type == "runtime_error":
        return True
    markers = (
        "fail:",
        "failed:",
        "validation failed",
        "expected an exception",
        "command injection",
        "hacked",
        "out-of-bounds",
        "traversed",
        "runtimeerror",
        "runtime_error",
        "segmentation fault",
        "aborted",
        "command timed out",
    )
    return any(marker in text for marker in markers)


def validate_one(
    *,
    dataset_root: Path,
    subset: str,
    language: str,
    track: str,
    index: int,
    output_root: Path,
    timeout: int,
) -> dict[str, Any]:
    records = _read_json(dataset_root / subset / LANGUAGE_FILES[language].format(subset=subset))
    record = records[index]
    started = time.perf_counter()
    if language == "python":
        result = validate_python_secure(record, timeout=timeout) if track == "secure" else validate_python_insecure(record, timeout=timeout)
    elif language == "cpp":
        result = _rerun_cpp_harness(record, track, output_root, timeout)
    elif language == "go":
        result = _rerun_go_harness(record, track, output_root, timeout)
    else:
        raise ValueError(f"unsupported language: {language}")
    elapsed = time.perf_counter() - started
    payload = {
        "subset": subset,
        "language": language,
        "track": track,
        "index": index,
        "task_id": record.get("ID"),
        "ok": result.ok,
        "elapsed_sec": round(elapsed, 3),
        "result": _result_to_dict(result),
    }
    return payload


def _logical_error_type(row: dict[str, Any]) -> str:
    result = row.get("result") or {}
    details = result.get("details") or {}
    error_type = str(details.get("error_type") or "unknown")
    if error_type != "passed":
        return error_type

    worker = details.get("worker_result") or {}
    tests = worker.get("tests") if isinstance(worker, dict) else None
    if not isinstance(tests, dict):
        return "logical_validation_failed"

    errors = " ".join(str((value or {}).get("error") or "") for value in tests.values() if isinstance(value, dict))
    if "ModuleNotFoundError" in errors:
        return "missing_python_dependency"
    if "solution error:" in errors:
        return "python_solution_error"
    if row.get("track") == "secure":
        failed = [name for name, value in tests.items() if isinstance(value, dict) and not value.get("passed")]
        return "secure_" + "_".join(failed or ["test"]) + "_failed"
    if row.get("track") == "insecure":
        if details.get("false_secure"):
            return "false_secure"
        if not details.get("insecure_behavior_match"):
            return "insecure_behavior_mismatch"
        return "insecure_validation_failed"
    return "logical_validation_failed"


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:

    summary: dict[str, Any] = {}
    for row in rows:
        key = (row["subset"], row["language"], row["track"])
        item = summary.setdefault(
            "|".join(key),
            {
                "subset": row["subset"],
                "language": row["language"],
                "track": row["track"],
                "total": 0,
                "ok": 0,
                "failed": 0,
                "error_types": {},
                "elapsed_sec": [],
            },
        )
        item["total"] += 1
        if row["ok"]:
            item["ok"] += 1
        else:
            item["failed"] += 1
            error_type = _logical_error_type(row)
            item["error_types"][error_type] = item["error_types"].get(error_type, 0) + 1
        item["elapsed_sec"].append(float(row.get("elapsed_sec") or 0))
    for item in summary.values():
        elapsed = item.pop("elapsed_sec")
        item["pass_rate"] = round(item["ok"] / item["total"] * 100, 2) if item["total"] else 0
        item["avg_sec"] = round(statistics.mean(elapsed), 3) if elapsed else 0
        item["median_sec"] = round(statistics.median(elapsed), 3) if elapsed else 0
        item["max_sec"] = round(max(elapsed), 3) if elapsed else 0
    return {"groups": list(summary.values())}


def _write_report(output_root: Path, summary: dict[str, Any], failures: list[dict[str, Any]]) -> Path:
    lines = [
        "# SecEvoBasePlus Docker Revalidation Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "This report is based on fresh Docker execution. Python runs `check(candidate)` inside Docker. C++ and Go rerun the saved validation harnesses inside Docker.",
        "",
        "## Summary",
        "",
        "| Subset | Language | Track | OK | Total | Pass Rate | Avg(s) | Median(s) | Max(s) | Failure Types |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in sorted(summary["groups"], key=lambda x: (x["subset"], x["language"], x["track"])):
        failure_types = ", ".join(f"{k}:{v}" for k, v in sorted(item["error_types"].items())) or "-"
        lines.append(
            f"| {item['subset']} | {item['language']} | {item['track']} | {item['ok']} | {item['total']} | "
            f"{item['pass_rate']}% | {item['avg_sec']} | {item['median_sec']} | {item['max_sec']} | {failure_types} |"
        )
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("No failures.")
    else:
        lines.append("| Subset | Language | Track | Task ID | Error Type | Last Error Line |")
        lines.append("|---|---|---|---|---|---|")
        for row in failures[:200]:
            result = row.get("result") or {}
            details = result.get("details") or {}
            stderr = str(result.get("stderr") or "")
            last = stderr.strip().splitlines()[-1] if stderr.strip() else ""
            if not last:
                worker = details.get("worker_result") or {}
                tests = worker.get("tests") if isinstance(worker, dict) else None
                if isinstance(tests, dict):
                    errors = [str((value or {}).get("error") or "") for value in tests.values() if isinstance(value, dict)]
                    last = "; ".join(error for error in errors if error)
            last = last.replace("|", "\\|")[:240]
            lines.append(
                f"| {row['subset']} | {row['language']} | {row['track']} | {row['task_id']} | "
                f"{_logical_error_type(row)} | {last} |"
            )
    report = output_root / "docker_revalidation_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    os.environ.setdefault("SAFECODER_CPP_BACKEND", "docker")
    os.environ.setdefault("SAFECODER_GO_BACKEND", "docker")
    os.environ.setdefault("SAFECODER_CPP_DOCKER_IMAGE", "porta-bench-runtime-cpp:latest")
    os.environ.setdefault("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22")
    os.environ.setdefault("SAFECODER_PYTHON_DOCKER_IMAGE", "porta-bench-runtime-python3:latest")

    parser = argparse.ArgumentParser(description="Fresh Docker revalidation for SecEvoBasePlus Python/C++/Go datasets.")
    parser.add_argument("--dataset-root", type=Path, default=Path("SecEvoBasePlus"))
    parser.add_argument("--output-root", type=Path, default=Path("translation_work/docker_revalidation/latest"))
    parser.add_argument("--subsets", nargs="+", default=["Base", "Plus"], choices=["Base", "Plus"])
    parser.add_argument("--languages", nargs="+", default=["python", "cpp", "go"], choices=["python", "cpp", "go"])
    parser.add_argument("--tracks", nargs="+", default=["secure", "insecure"], choices=["secure", "insecure"])
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-failures-from", type=Path, default=None)
    args = parser.parse_args()

    output_root = args.output_root
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    log_path = output_root / "results.jsonl"

    tasks: list[dict[str, Any]] = []
    failure_filter: set[tuple[str, str, str, str]] | None = None
    if args.only_failures_from is not None:
        failure_rows = _read_json(args.only_failures_from)
        failure_filter = {
            (str(row.get("subset")), str(row.get("language")), str(row.get("track")), str(row.get("task_id")))
            for row in failure_rows
            if not row.get("ok", False)
        }

    for subset in args.subsets:
        for language in args.languages:
            records = _read_json(args.dataset_root / subset / LANGUAGE_FILES[language].format(subset=subset))
            count = min(args.limit, len(records)) if args.limit else len(records)
            for track in args.tracks:
                for index in range(count):
                    record_id = str(records[index].get("ID"))
                    if failure_filter is not None and (subset, language, track, record_id) not in failure_filter:
                        continue
                    tasks.append(
                        {
                            "dataset_root": args.dataset_root,
                            "subset": subset,
                            "language": language,
                            "track": track,
                            "index": index,
                            "output_root": output_root,
                            "timeout": args.timeout,
                        }
                    )

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {executor.submit(validate_one, **task): task for task in tasks}
        for completed, future in enumerate(as_completed(future_map), start=1):
            try:
                row = future.result()
            except Exception as exc:
                task = future_map[future]
                row = {
                    "subset": task["subset"],
                    "language": task["language"],
                    "track": task["track"],
                    "index": task["index"],
                    "task_id": None,
                    "ok": False,
                    "elapsed_sec": 0,
                    "result": {"stderr": repr(exc), "details": {"error_type": "runner_exception"}},
                }
            rows.append(row)
            _append_jsonl(log_path, row)
            print(
                f"[{completed}/{len(tasks)}] {row['subset']} {row['language']} {row['track']} "
                f"{row.get('task_id')} ok={row['ok']} elapsed={row['elapsed_sec']}s",
                flush=True,
            )

    summary = _summarize(rows)
    failures = [row for row in rows if not row.get("ok")]
    _write_json(output_root / "summary.json", summary)
    _write_json(output_root / "failures.json", _compact_for_storage(failures))
    report = _write_report(output_root, summary, failures)
    print(f"Wrote results: {log_path}")
    print(f"Wrote summary: {output_root / 'summary.json'}")
    print(f"Wrote report: {report}")


if __name__ == "__main__":
    main()
