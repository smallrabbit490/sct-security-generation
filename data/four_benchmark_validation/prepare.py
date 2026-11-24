from pathlib import Path
import csv, json, sys, shutil

ROOT = Path.cwd()
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from methods.secodeplt_eval.template import UNITTEST_TEMPLATE, generate_test_code
from translation_pipeline.python_validator import _worker_source, get_python_suites

work = ROOT / "translation_work/validation_runs/four_benchmark_20261124"
data = ROOT / "data"
with (PACKAGE / "tasks.csv").open(encoding="utf8", newline="") as manifest_file:
    tasks = list(csv.DictReader(manifest_file))


def read_rows(name):
    return [dict(task_id=row["id"]) for row in tasks if row["group"] == name]


manifest = []
plt = {
    str(r["index"]): r
    for r in json.loads(
        (data / "external/secodeplt/secodeplt/data.json").read_text(encoding="utf8")
    )
}
for row in read_rows("plt"):
    r = plt[str(row["task_id"])]
    g = r["ground_truth"]
    u = r["unittest"]
    key = str(row["task_id"])
    p = work / "plt" / key
    p.mkdir(parents=True, exist_ok=True)
    code = "".join(
        g.get(s) or "" for s in ("code_before", "patched_code", "code_after")
    )
    (p / "test.py").write_text(
        generate_test_code(
            UNITTEST_TEMPLATE,
            u["setup"],
            code,
            u["testcases"],
            r["task_description"]["function_name"],
        ),
        encoding="utf8",
    )
    manifest.append(dict(group="plt", id=key, language="python", reference=bool(code)))
(work / "worker.py").write_text(_worker_source(), encoding="utf8")
for subset in ("Base", "Plus"):
    group = f"codeseceval-{subset.lower()}"
    records = {
        r["ID"]: r
        for r in json.loads(
            (data / f"SecEvoBasePlus/{subset}/Python_{subset}.json").read_text(
                encoding="utf8"
            )
        )
    }
    for row in read_rows(group):
        key = row["task_id"]
        r = records[key]
        p = work / group / key
        p.mkdir(parents=True, exist_ok=True)
        f, s = get_python_suites(r)
        (p / "spec.json").write_text(
            json.dumps(
                dict(
                    solution=r["Secure Code"],
                    entry_point=r["Entry_Point"],
                    tests=dict(fp=f, sp=s),
                )
            ),
            encoding="utf8",
        )
        manifest.append(
            dict(
                group=group,
                id=key,
                language="python",
                reference=bool(r["Secure Code"]),
                functional=bool(f),
                security=bool(s),
            )
        )
for lang in ("python", "c", "cpp", "java"):
    for line in (
        (data / f"external/autosuit/upstream_20261118/{lang}/test.jsonl")
        .read_text(encoding="utf8")
        .splitlines()
    ):
        r = json.loads(line)
        key = r["id"]
        p = work / "autosuit" / key
        p.mkdir(parents=True, exist_ok=True)
        code = r["secure_code"] or ""
        (p / Path(r["code_file_name"]).name).write_text(code, encoding="utf8")
        row = dict(
            group="autosuit",
            id=key,
            language=lang,
            reference=bool(code.strip()),
            source=Path(r["code_file_name"]).name,
        )
        for suite in ("functional", "security"):
            name = r[f"{suite}_test_file"]
            test = r[f"{suite}_test"]
            row[suite] = Path(name).name if name and test else None
            if row[suite]:
                (p / row[suite]).write_text(test, encoding="utf8")
        manifest.append(row)
source = data / "external/cweval/upstream_20261117"
shutil.copytree(source, work / "cweval", dirs_exist_ok=True)
for r in read_rows("cweval"):
    key = r["task_id"]
    tests = [key.rsplit("_task.", 1)[0] + "_test.py"]
    manifest.append(
        dict(
            group="cweval",
            id=key,
            language=Path(key).suffix[1:],
            reference=True,
            tests=tests,
        )
    )
assert len(manifest) == len({(r["group"], r["id"]) for r in manifest}) == 2199
assert {(r["group"], r["id"], r["language"]) for r in manifest} == {
    (r["group"], r["id"], r["language"]) for r in tasks
}
(work / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
