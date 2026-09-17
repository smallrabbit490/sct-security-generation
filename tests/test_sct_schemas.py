import json

from methods.sct_agent.schemas import ExperienceCard, GateRecord, ValidationEvidence


def test_validation_and_gate_records_round_trip():
    evidence = ValidationEvidence.compile_pass("python")
    card = ExperienceCard(
        cwe="cwe-22",
        applicability="路径输入来自外部参数",
        principle="限制规范化路径",
        implementation_hints={"python": "resolve/relative_to"},
        forbidden_patterns="禁止前缀判断",
    )
    record = GateRecord(
        candidate_id="cand-1",
        evidence=evidence,
        delta_joint_pass=0.1,
        h_pass_security_regressions=0,
        decision="promote",
        reasons=["joint pass improved"],
    )
    restored = GateRecord.from_dict(json.loads(json.dumps(record.to_dict())))
    assert restored.decision == "promote"
    assert card.to_dict()["principle"] == "限制规范化路径"

