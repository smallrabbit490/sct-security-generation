"""零API公开关系核对与规格检查。只输出公开题面，不把夹具/参考转换成新指令。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    cfg = ROOT / 'configs/cle_v41_relation_20261026'
    protocol = read(cfg / 'protocol.json')
    raw = read(ROOT / protocol['source_file'])
    original = next(row for row in raw if str(row['index']) == '1409')
    snapshot = next(row for row in read(ROOT / protocol['previous_snapshot']) if str(row['index']) == '1409')
    public = original['task_description']
    assert public == snapshot['task_description']
    assert snapshot['family_id'] == protocol['family_id']
    assert 'global dictionary' in public['context'] and 'signature of the file' in public['arguments']
    assert protocol['paid_execution_enabled'] is False and protocol['execution_ready'] is False
    assert len(protocol['arms']) * protocol['repeats'] == protocol['planned_P7_runs'] == 8
    schedule = read(cfg / 'schedule.json')
    assert len(schedule) == len({row['cell_id'] for row in schedule}) == 8
    assert sum(row['group'] == 'technical' for row in schedule) == 4
    assert all(row['task_id'] == '1409' and row['family_id'] == protocol['family_id'] for row in schedule)
    assert {row['arm'] for row in schedule[:4]} == set(protocol['arms'])
    assert protocol['max_code_generations'] == 16 and protocol['task_ids'] == ['1409']
    assert len(protocol['generic_reminder'].split()) == len(protocol['relation_reminder'].split()) == 54
    for payload in (protocol['generic_reminder'], protocol['relation_reminder']):
        assert 'VALID_SIGNATURES[' not in payload and '.get(file_name)' not in payload
        assert 'sha256' not in payload.lower() and '/tmp/' not in payload
    prior = ROOT / 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2'
    prompt_evidence = []
    for path in sorted((prior / 'journals/1409_r1_D/requests').glob('*.json')):
        record = read(path)
        if not record['prompt'].startswith('Generate complete runnable Python code; output code only.'):
            continue
        # 从实际历史生成提示确认要求是否已存在，摘录不包含测试或签名值。
        extracts = re.findall(r'.{0,40}(?:bind the supplied signature to the specific file_name|entry must still be bound to file_name).{0,90}', record['prompt'])
        prompt_evidence.append({'journal': str(path.relative_to(ROOT)).replace('\\', '/'),
                               'file_specific_requirement_present': bool(extracts), 'extracts': extracts})
    assert any(row['file_specific_requirement_present'] for row in prompt_evidence)
    checks = [
        {'field': 'context', 'quote': public['context'], 'classification': 'explicit',
         'supports': 'existing external dictionary storing allowed-file signatures; preserve object',
         'does_not_specify': 'whether keys are paths/names/signatures, or how values are structured'},
        {'field': 'arguments', 'quote': public['arguments'], 'classification': 'explicit with semantic entailment',
         'supports': 'signature describes the same file as file_name in this invocation'},
        {'field': 'security_policy', 'quote': public['security_policy'], 'classification': 'semantic entailment',
         'supports': 'the requested file must have a valid signature, not merely an unrelated trusted signature'},
        {'field': 'return', 'quote': public['return'], 'classification': 'explicit',
         'supports': 'binary result based on file-signature validity; no algorithm/key layout given'},
    ]
    out = {
        'date_Asia_Shanghai': '2026-10-26', 'task_id': '1409', 'family_id': protocol['family_id'],
        'source': protocol['source_file'], 'original_public_equals_previous_model_public': True,
        'public_task': public, 'public_evidence': checks,
        'decision': 'semantic file-specific relation supported; dictionary layout and concrete verification procedure not determined',
        'semantic_reminder_eligible': True, 'schema_specific_hard_check_eligible': False,
        'unknowns': protocol['public_contract_scope']['not_explicit'],
        'prior_generation_prompt_evidence': prompt_evidence,
        'why_not_missing_knowledge': 'the failed repair generation request already contains the per-file relation; a new reminder tests salience/implementation, not newly supplied factual knowledge',
        'investment_recommendation': protocol['investment_recommendation'],
        'specification_check': {'status': 'passed', 'planned_P7': 8, 'max_codes': 16,
                                'technical_included': 4, 'schedule_unique': True,
                                'reminder_words_each': 54, 'paid_enabled': False,
                                'offline_wiring_implemented': protocol.get('offline_wiring_ready', False),
                                'paid_entry_implemented': False},
        'current_operation': {'model_API_calls': 0, 'embedding_calls': 0, 'new_generations': 0,
                              'dataset_changed': False, 'cards_or_Q_changed': False,
                              'original_unittest_or_ground_truth_used_to_construct_new_prompt': False},
    }
    target = ROOT / 'results/curated/cle_v41_relation_plan_20261026/public_contract_audit.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'audit': str(target), 'public_semantics_supported': True,
                      'schema_fully_specified': False, 'planned_P7': 8, 'API_calls': 0,
                      'recommendation': 'HOLD_PAID'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
