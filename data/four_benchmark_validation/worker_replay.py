import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

work = Path("/work")


def execute(argv, cwd, env=None, timeout=25):
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", ""


def status(result):
    return {
        "exit": result[0],
        "status": "pass"
        if result[0] == 0
        else "timeout"
        if result[0] == 124
        else "error",
    }


def pytest_result(args, path):
    result = execute(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--timeout=8",
            *args,
        ],
        path,
        timeout=35,
    )
    counts = {
        label: int(n)
        for n, label in re.findall(
            r"(\d+) (passed|failed|errors?|skipped|deselected)",
            result[1].splitlines()[-1] if result[1].splitlines() else "",
        )
    }
    outcome = status(result)
    outcome.update(counts)
    if not counts.get("passed") and outcome["status"] == "pass":
        outcome["status"] = "no_assertions"
    return outcome


def java_suite(path, row, test, classes):
    cp = f"/java/*:/java/lib/*:{classes}"
    build = execute(
        [
            "javac",
            "-encoding",
            "UTF-8",
            "-d",
            str(classes),
            "-cp",
            cp,
            row["source"],
            test,
        ],
        path,
    )
    outcome = {**status(build), "stage": "compile"}
    if not build[0]:
        result = execute(
            [
                "java",
                "-cp",
                cp,
                "org.junit.platform.console.ConsoleLauncher",
                f"--scan-class-path={classes}",
                "--fail-if-no-tests",
                "--disable-ansi-colors",
            ],
            path,
        )
        outcome = {**status(result), "stage": "test"}
    return outcome


def check(row):
    group, key = row["group"], row["id"]
    path = work / group / key
    if group == "plt":
        target = path / "result.json"
        result = execute(
            [sys.executable, "-I", "test.py"],
            path,
            {**os.environ, "UNITTEST_RESULTS_PATH": str(target)},
        )
        if result[0]:
            msg = result[2].strip().splitlines()
            category = msg[-1].split(":", 1)[0] if msg else ""
            return {
                **status(result),
                "error_category": category if category.isidentifier() else "",
            }
        payload = json.loads(target.read_text())
        suites = {
            k: {"total": len(payload[k]), "passed": payload[k].count(1)}
            for k in ("capability", "safety")
        }
        return {
            "status": "pass"
            if all(v["total"] and v["passed"] == v["total"] for v in suites.values())
            else "reference_failed",
            **suites,
        }
    if group.startswith("codeseceval"):
        result = execute([sys.executable, "-I", "/work/worker.py", "spec.json"], path)
        if result[0]:
            return status(result)
        payload = json.loads(result[1].strip().splitlines()[-1])
        suites = {k: v["passed"] for k, v in payload["tests"].items()}
        return {
            "status": "pass" if all(suites.values()) else "reference_failed",
            "loaded": payload["compile"],
            **suites,
        }
    if group == "autosuit":
        if not row["reference"]:
            return {"status": "missing_reference"}
        outcomes = {}
        for suite in ("functional", "security"):
            test = row[suite]
            if not test:
                outcomes[suite] = {"status": "missing_test"}
            elif row["language"] == "python":
                outcomes[suite] = pytest_result([test], path)
            elif row["language"] in ("c", "cpp"):
                compiler = "gcc" if row["language"] == "c" else "g++"
                build = execute(
                    [compiler, "-DUNIT_TEST", test, "-o", str(path / "as-suite")], path
                )
                outcome = status(build)
                outcome["stage"] = "compile"
                if not build[0]:
                    result = execute([str(path / "as-suite")], path)
                    outcome = {**status(result), "stage": "test"}
                    match = re.search(
                        r"tests failed:\s*(\d+),\s*tests passed:\s*(\d+)",
                        result[1],
                        re.I,
                    )
                    if match:
                        failed, passed = map(int, match.groups())
                        outcome.update(failed=failed, passed=passed)
                        if failed or not passed:
                            outcome["status"] = "reference_failed"
                    elif outcome["status"] == "pass":
                        outcome["status"] = "no_assertions"
                outcomes[suite] = outcome
            else:
                with tempfile.TemporaryDirectory(prefix="junit-") as directory:
                    outcomes[suite] = java_suite(path, row, test, Path(directory))
                continue
        return {
            "status": "pass"
            if all(v["status"] == "pass" for v in outcomes.values())
            else "incomplete_or_failed",
            **outcomes,
        }
    if not row["tests"]:
        return {"status": "missing_test"}
    if row["language"] in ("c", "cpp", "go"):
        compiled = (work / "cweval" / "benchmark" / key).parent / "compiled"
        compiled.mkdir(exist_ok=True)
        output = compiled / Path(key).stem
        command = "from cweval.commons import compile_src; import sys; sys.exit(compile_src(sys.argv[1],sys.argv[2],check=False)[0])"
        build = execute(
            [sys.executable, "-c", command, f"benchmark/{key}", str(output)],
            work / "cweval",
            timeout=40,
        )
        if build[0]:
            return {**status(build), "stage": "compile"}
    return {
        **pytest_result(
            [
                f"benchmark/{row['tests'][0]}",
                "-m",
                "functionality or security",
                "-k",
                "not unsafe",
            ],
            work / "cweval",
        ),
        "stage": "test",
    }


rows = json.loads((work / "manifest.json").read_text())
selection = set(sys.argv[1:])
with (work / os.environ.get("REPLAY_OUTPUT", "rows.jsonl")).open(
    "w", encoding="utf8", buffering=1
) as output:
    for index, row in enumerate(rows, 1):
        if selection and not (
            {row["group"], row["group"] + ":" + row["language"]} & selection
        ):
            continue
        try:
            outcome = check(row)
        except Exception as err:
            outcome = {"status": "runner_error", "error_category": type(err).__name__}
        print(
            json.dumps({**{k: row[k] for k in ("group", "id", "language")}, **outcome}),
            file=output,
        )
        if index % 50 == 0:
            print("processed", index, flush=True)
