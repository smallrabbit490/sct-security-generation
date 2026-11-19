"""检查发布材料的引用、计数、抽样及敏感凭据；仅输出汇总。"""
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data/audit_release_20261118"


def readlines(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    labels = [r for p in (D / "labels").glob("*.jsonl") for r in readlines(p)]
    assert len(labels) == 5433
    bykey = {r["key"]: r for r in labels}
    assert len(bykey) == len(labels)
    for r in labels:
        assert r["verdict"] in ("合格", "有缺陷", "无法判定")
        assert (r["defect_type"] is not None) == (r["verdict"] == "有缺陷")
    materials = [r for p in (D / "materials").glob("*.jsonl") for r in readlines(p)]
    assert len({p["key"] for p in materials}) == len(materials) == 4692
    assert all(p["key"] in bykey for p in materials)
    sample = readlines(D / "human_review_150/model_labels.jsonl")
    packets = readlines(D / "human_review_150/blinded_tasks.jsonl")
    assert len(sample) == len(packets) == len({r["key"] for r in sample}) == 150
    assert all(r["verdict"] == "有缺陷" and r["review_status"] == "双判一致" for r in sample)
    assert {r["review_id"] for r in sample} == {r["review_id"] for r in packets}
    counts = collections.Counter(r["bank"] for r in sample)
    assert counts["PLT"] == 60 and counts["CodeSecEval-Base"] == 40 and counts["CodeSecEval-Plus"] == 20
    manifest = json.loads((D / "release_manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((D / "prompts/external_six_rules_system.txt").read_bytes()).hexdigest() == manifest["six_rule_protocol_sha256"]
    # 比对本地真实凭据值，仅报告命中文件数，绝不打印密钥。
    secret = (ROOT / "local_secrets/yibuapi/使用说明.md").read_text(encoding="utf-8")
    values = re.findall(r'"api_key"\s*:\s*"([^"]+)"', secret)
    assert all(not any(v.encode() in p.read_bytes() for v in values) for p in D.rglob("*") if p.is_file())
    print(json.dumps({"verified_tasks": len(labels), "material_tasks": len(materials),
                      "review_tasks": len(sample), "verdicts": dict(collections.Counter(r["verdict"] for r in labels)),
                      "sample": dict(counts)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
