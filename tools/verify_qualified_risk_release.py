"""核验原合格标签不变、复核身份和逐字证据、交集抽样与人工题包。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import qualified_risk_audit as audit
from schema import request_identity


def main():
    d = audit.RELEASE
    rows = audit.jsonlines(d / "all_659_risk_labels.jsonl")
    payloads = {p["key"]: p for p in audit.jsonlines(d / "audit_materials_659.jsonl")}
    assert len(rows) == len(payloads) == len({r["key"] for r in rows}) == 659
    manifest = audit.read(d / "frozen_manifest.json")
    assert hashlib.sha256((d / "audit_materials_659.jsonl").read_bytes()).hexdigest() == manifest["payloads_sha256"]
    assert hashlib.sha256((d / "history_all_659.jsonl").read_bytes()).hexdigest() == manifest["history_sha256"]
    for slug, sha in manifest["original_labels"].items():
        p = ROOT / "data/audit_release_20261118/labels" / (slug + ".jsonl")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == sha
    original = {}
    for slug in manifest["original_labels"]:
        original.update({r["key"]: r for r in audit.jsonlines(ROOT / "data/audit_release_20261118/labels" / (slug + ".jsonl"))})
    for r in rows:
        assert r["original_verdict"] == original[r["key"]]["verdict"] == "合格"
        p = payloads[r["key"]]
        assert set(p) <= {"key", "bank", "language", "oracle", "sources", "test_provenance"}
        assert all(s["role"] in ("public", "test") for s in p["sources"])
        for i, label in enumerate(r["judgments"], 1):
            assert r["identities"][i - 1] == request_identity(p, "gpt-6.1-sol", audit.PROTOCOL, i)
            if label:
                assert not audit.validate(label, p)
        assert r["risk_consensus"] == audit.consensus(r["judgments"])["risk_consensus"]
        assert r["history"]["low_performance"] == audit.history_summary(r["history"]["evidence"])["low_performance"]
    selected = audit.jsonlines(d / "selected_intersection.jsonl")
    assert selected == audit.select_intersection(rows)
    assert len(selected) <= 50 and len({r["key"] for r in selected}) == len(selected)
    assert all(r["risk_consensus"] and r["history"]["low_performance"] for r in selected)
    packets = audit.jsonlines(d / "blinded_tasks.jsonl")
    models = audit.jsonlines(d / "model_labels.jsonl")
    assert len(selected) == len(packets) == len(models)
    assert {p["material"]["key"] for p in packets} == {r["key"] for r in selected}
    assert all(set(p) == {"review_id", "material"} for p in packets)
    assert all(m["verdict"] == "合格" and m["defect_type"] is None for m in models)
    summary = audit.read(d / "summary.json")
    assert summary["valid_judgments"] == sum(r["valid_judgments"] for r in rows)
    assert summary["selected"] == len(selected)
    for bank, s in summary["by_bank"].items():
        sub = [r for r in rows if r["bank"] == bank]
        assert s["tasks"] == len(sub)
        assert s["historical_low"] == sum(r["history"]["low_performance"] for r in sub)
        assert s["risk_consensus"] == sum(r["risk_consensus"] for r in sub)
        assert s["intersection"] == sum(r["risk_consensus"] and r["history"]["low_performance"] for r in sub)
        assert s["selected"] == sum(r["bank"] == bank for r in selected)
    assert hashlib.sha256((d / "system_prompt.txt").read_bytes()).hexdigest() == audit.PROTOCOL
    secrets = (ROOT / "local_secrets/yibuapi/使用说明.md").read_text(encoding="utf-8")
    values = re.findall(r'"api_key"\s*:\s*"([^"]+)"', secrets)
    assert all(not any(v.encode() in p.read_bytes() for v in values) for p in d.rglob("*") if p.is_file())
    print(json.dumps({"verified_tasks": len(rows), "valid_judgments": sum(r["valid_judgments"] for r in rows),
                      "selected": len(selected), "by_bank": audit.read(d / "summary.json")["by_bank"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
