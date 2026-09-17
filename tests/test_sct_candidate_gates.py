from methods.sct_agent.candidate_gates import decide_candidate


def test_gate_requires_positive_joint_pass_and_no_hpass_regression():
    assert decide_candidate(0.0, 0.0, 0.0).decision == "reject"
    assert decide_candidate(0.2, 0.0, 0.0).decision == "promote"
    assert decide_candidate(0.2, 0.1, 0.0).decision == "reject"

