"""验证决策报告不会把未执行、未复核或技术失败写成Q性能失败。"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SPEC = spec_from_file_location(
    'cle_q_full_test_decision',
    Path(__file__).resolve().parents[1] / 'configs/cle_q_full_test_decision_20261017/snapshot.py',
)
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize('gate_b,gate_d,summary,code_reviewed,confirmation_reviewed,expected', [
    ({'passed': False}, None, {}, False, False, 'WAIT_HUMAN'),
    ({'passed': False, 'reason': 'no_direct_positive_in_calibration_stop'}, None, {}, False, False, 'STOP_COVERAGE'),
    ({'passed': False, 'reason': 'calibration_contract_defect_no_API'}, None, {}, False, False, 'STOP_TECHNICAL'),
    ({'passed': True}, None, {}, False, False, 'WAIT_DEVELOPMENT'),
    ({'passed': True}, {'complete': False, 'technical_gate': False}, {}, False, False, 'STOP_TECHNICAL'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': False}, {}, False, False, 'WAIT_CODE_REVIEW'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': False, 'retrieval_passed': True}, {}, True, False, 'STOP_Q_DEVELOPMENT'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': True}, {}, True, False, 'WAIT_CONFIRMATION'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': True}, {'confirmation_run': True}, True, False, 'WAIT_CONFIRMATION_REVIEW'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': True},
     {'confirmation_run': True, 'confirmation_conclusion': 'Q_benefit_not_established'}, True, True, 'STOP_Q_CONFIRMATION'),
    ({'passed': True}, {'complete': True, 'technical_gate': True, 'q_passed': True},
     {'confirmation_run': True, 'confirmation_conclusion': 'supported_Q_benefit_under_protocol'}, True, True, 'SCIENTIFIC_SIGNAL_CHECK_FUNCTION'),
])
def test_decision_requires_actual_stage_evidence(gate_b, gate_d, summary, code_reviewed, confirmation_reviewed, expected):
    state, reason = MODULE.research_decision(
        gate_b, gate_d, summary, code_reviewed=code_reviewed,
        confirmation_reviewed=confirmation_reviewed,
    )
    assert state == expected
    assert reason
