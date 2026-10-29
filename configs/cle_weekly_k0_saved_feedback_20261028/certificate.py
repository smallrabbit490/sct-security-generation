"""只接纳本次明确授权的K0历史反馈证书；不把它称为动态验证一致。"""
import hashlib
import json
from pathlib import Path

RELATIVE = 'FQ_LEARN/K0/saved_feedback_replay_20261028'
STATUS = 'passed_saved_response_and_historical_feedback_replay'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def accepted(root):
    root = Path(root)
    path = root / RELATIVE / 'certificate.json'
    if not path.is_file():
        return False
    value = read(path)
    if (value.get('status') != STATUS or value.get('stage') != 'K0'
            or value.get('mode') != 'saved_responses_and_historical_validation_feedback'
            or value.get('completed') != 303 or value.get('planned') != 303
            or value.get('new_HTTP') != 0 or value.get('dynamic_revalidation_executed') is not False
            or value.get('dynamic_validation_all_consistent') is not False):
        return False
    required = ('all_non_timing_row_fields_equal', 'all_saved_model_requests_consumed',
                'Q_events_equal', 'frozen_Q_visits_and_card_bodies_equal', 'original_evidence_unchanged')
    if not all(value.get(key) is True for key in required):
        return False
    if not value.get('evidence') or not all(Path(p).is_file() for p in value['evidence']):
        return False
    for name, expected in value['input_sha256'].items():
        if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            return False
    ids = read(root / 'manifest.json')['pools']['D_init']
    audit = read(root / RELATIVE / 'per_task_audit.json')
    if [item['task_id'] for item in audit] != ids or len(audit) != 303:
        return False
    if not all(item['all_non_timing_row_fields_equal'] and item['Q_events_equal'] for item in audit):
        return False
    if sum(len(item['consumed_request_identities']) for item in audit) != value['model_requests_consumed']:
        return False
    feedback = read(root / RELATIVE / 'feedback_audit.json')
    native = read(root / RELATIVE / 'replay_result.json')
    return (len(feedback) == value['historical_feedback_calls']
            and native.get('status') == 'passed' and native.get('completed') == 303
            and native.get('new_HTTP') == 0)
