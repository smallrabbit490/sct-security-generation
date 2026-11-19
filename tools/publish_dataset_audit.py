"""离线发布审计标签和人工复核题包；不请求API，不执行第三方样本。"""
import ast
import collections
import csv
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/external_bank_audit"))
from schema import request_identity, validate_result
from run import SYSTEM, PROTOCOL

OUT = ROOT / "data/audit_release_20261118"
RESTRICTED = {"SecurityEval", "LLMSecEval", "PythonSecurityEval"}
NORMALIZE = {"接口契约缺失": "接口契约", "业务规则或数据缺失": "业务规则或数据"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks, rows = {}, []
    legacy = ROOT / "translation_work/diagnostics/20261117/bank_verdict_final"
    for p in lines(legacy / "payloads.jsonl"):
        tasks[p["key"]] = p
        safe_key = p["key"].replace("/", "_").replace("\\", "_")
        records = [load(legacy / "responses" / f'{safe_key}__s{i}.json') for i in (1, 2)]
        a, b = [r["parsed"] for r in records]
        verdict = a["verdict"]
        rows.append(dict(key=p["key"], bank=p["bank"], language="python",
                         verdict=verdict, defect_type=NORMALIZE.get(a.get("defect_type"), a.get("defect_type")) if verdict == "有缺陷" else None,
                         label_protocol="bank-verdict-v2-20261117-primary",
                         review_status="双判一致" if (a["verdict"], a.get("defect_type")) == (b["verdict"], b.get("defect_type")) else "双判分歧_保留历史首判",
                         valid_judgments=2, test_integrity=a["test_integrity"], test_quality=a["test_quality"],
                         judgments=[a, b], evidence_status="历史解释_未逐字证据校验",
                         model=records[0]["model"], identities=[f'{p["key"]}__s{i}' for i in (1, 2)]))
    for directory in ["20261117/external_bank_audit", "20261118/candidate_six_rule_audit"]:
        d = ROOT / "translation_work/diagnostics" / directory
        for p in lines(d / "payloads.jsonl"):
            tasks[p["key"]] = p
            judgments, identities = [], []
            for i in (1, 2):
                identity = request_identity(p, "gpt-6.1-sol", PROTOCOL, i)
                identities.append(identity)
                f = d / "responses" / (identity + ".json")
                r = load(f) if f.exists() else {}
                a = r.get("parsed")
                judgments.append(a if r.get("status") == "ok" and a and not validate_result(a, p) else None)
            a, b = judgments
            verdict, defect = "无法判定", None
            status = "缺测" if not (a and b) else "双判分歧"
            if a and b and a["verdict"] == b["verdict"] and (a["verdict"] != "有缺陷" or a.get("defect_type") == b.get("defect_type")):
                verdict, defect, status = a["verdict"], a.get("defect_type"), "双判一致"
            if p.get("full_context_available") is False:
                verdict, defect, status = "无法判定", None, "材料不全"
            fields = {k: a[k] if a and b and a[k] == b[k] else "无法判定" for k in ("test_integrity", "test_quality")}
            rows.append(dict(key=p["key"], bank=p["bank"], language=p["language"],
                             verdict=verdict, defect_type=defect if verdict == "有缺陷" else None,
                             label_protocol="six-rules-" + PROTOCOL, review_status=status,
                             valid_judgments=sum(x is not None for x in judgments),
                             **fields, judgments=judgments, evidence_status="schema与逐字引文校验_非人工金标",
                             model="gpt-6.1-sol", identities=identities))
    assert len(rows) == 5433 and len(tasks) == len(rows)
    index = []
    for bank in sorted({r["bank"] for r in rows}):
        sub = [r for r in rows if r["bank"] == bank]
        slug = bank.lower().replace("+", "_plus")
        write_jsonl(OUT / "labels" / (slug + ".jsonl"), sub if bank not in RESTRICTED else [
            {k: v for k, v in r.items() if k != "judgments"} for r in sub])
        if bank not in RESTRICTED:
            write_jsonl(OUT / "materials" / (slug + ".jsonl"), [tasks[r["key"]] for r in sub])
        c = collections.Counter(r["verdict"] for r in sub)
        index.append(dict(dataset=bank, tasks=len(sub), qualified=c["合格"], defective=c["有缺陷"], uncertain=c["无法判定"],
                          valid_judgments=sum(r["valid_judgments"] for r in sub),
                          missing_pairs=sum(r["valid_judgments"] < 2 for r in sub),
                          materials="本地上游恢复_许可未明确" if bank in RESTRICTED else "materials/" + slug + ".jsonl"))
    write_csv(OUT / "dataset_index.csv", index)
    (OUT / "dataset_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    # 固定名单，以库/缺陷类型/语言分层轮转；仅抽双判类型一致的机器缺陷。
    eligible = [r for r in rows if r["verdict"] == "有缺陷" and r["bank"] not in RESTRICTED
                and r["review_status"] == "双判一致"]
    rng = random.Random(20261118)

    def pick(pool, n):
        strata = collections.defaultdict(list)
        for r in sorted(pool, key=lambda x: x["key"]):
            strata[(r["bank"], r["defect_type"], r["language"])].append(r)
        for group in strata.values():
            rng.shuffle(group)
        chosen = []
        while len(chosen) < n:
            progressed = False
            for key in sorted(strata):
                if strata[key] and len(chosen) < n:
                    chosen.append(strata[key].pop())
                    progressed = True
            if not progressed:
                raise ValueError(f"insufficient eligible defects: {len(chosen)}/{n}")
        return chosen

    selected = []
    for bank, n in [("PLT", 60), ("CodeSecEval-Base", 40), ("CodeSecEval-Plus", 20)]:
        selected += pick([r for r in eligible if r["bank"] == bank], n)
    selected += pick([r for r in eligible if r["bank"] not in {"PLT", "CodeSecEval-Base", "CodeSecEval-Plus"}], 30)
    rng.shuffle(selected)
    review = OUT / "human_review_150"
    review.mkdir(exist_ok=True)
    labels, packets, blank = [], [], []
    for i, r in enumerate(selected, 1):
        rid = f"HR-{i:03}"
        labels.append(dict(review_id=rid, **r))
        p = tasks[r["key"]]
        # 第一阶段不显示模型结论与参考答案；仅分离公开输入和评审可见测试。
        material = ({k: v for k, v in p.items() if k != "reference"} if "public" in p else
                    {**p, "sources": [s for s in p["sources"] if not s["role"].startswith("reference")]})
        packets.append(dict(review_id=rid, material=material))
        blank.append(dict(review_id=rid, annotator="", human_verdict="", human_defect_type="",
                          assertion_or_call="", missing_requirement="", why_not_inferable="",
                          human_test_integrity="", human_test_quality="", type_consistency="",
                          disagreement_reason="", confidence="", notes=""))
    write_jsonl(review / "blinded_tasks.jsonl", packets)
    write_jsonl(review / "model_labels.jsonl", labels)
    write_csv(review / "annotation_template.csv", blank)
    booklet = ["# 人工盲审题册（150条）", "", "先独立标注，再打开model_labels.jsonl核对类型。", ""]
    for packet in packets:
        booklet += ["## " + packet["review_id"], "", "```json",
                    json.dumps(packet["material"], ensure_ascii=False, indent=2), "```", ""]
    (review / "review_booklet.md").write_text("\n".join(booklet), encoding="utf-8")
    promptdir = OUT / "prompts"
    promptdir.mkdir(exist_ok=True)
    (promptdir / "external_six_rules_system.txt").write_bytes(SYSTEM.encode("utf-8"))
    (promptdir / "external_user_template.txt").write_text(
        'json.dumps(payload, ensure_ascii=False) + "\\n独立判断编号：" + str(sample)\n'
        "sample取1、2；payload原文在materials，许可未明确库按恢复清单本地读取。\n", encoding="utf-8")
    source = (ROOT / "tools/classify_bank_verdict.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    system_node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SYSTEM" for t in n.targets))
    render_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render")
    (promptdir / "legacy_v2_system.txt").write_text(ast.literal_eval(system_node.value), encoding="utf-8")
    (promptdir / "legacy_v2_user_renderer.py").write_text(ast.get_source_segment(source, render_node), encoding="utf-8")
    manifest = dict(total_tasks=len(rows), sampled_tasks=len(selected), selection_seed=20261118,
                    sample_counts=dict(collections.Counter(r["bank"] for r in selected)),
                    six_rule_protocol_sha256=PROTOCOL, legacy_aggregation="v2首判，保留第二判与分歧",
                    currency_cost="未测量", dynamic_validation="未在发布阶段执行",
                    inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in [legacy / "payloads.jsonl",
                                      ROOT / "translation_work/diagnostics/20261117/external_bank_audit/payloads.jsonl",
                                      ROOT / "translation_work/diagnostics/20261118/candidate_six_rule_audit/payloads.jsonl"]})
    (OUT / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"datasets": index, "sample": manifest["sample_counts"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
