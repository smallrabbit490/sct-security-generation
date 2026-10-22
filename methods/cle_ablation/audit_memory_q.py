"""只读核对Q实验原生逐题格式、远程统计重算及采用奖励对应；不请求模型。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.run_artifacts import write_json_atomic


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def check_run(directory):
    """检查实验消费者实际需要的字段和数值对应，错误直接失败，不补造缺项。"""
    metadata = json.loads((directory/'run_metadata.json').read_text(encoding='utf-8'))
    rows = read_rows(directory/'rows.jsonl')
    stage = metadata['args']['stage']
    arms = ['Q0'] if stage == 'learn' else metadata['args'].get('arms', ['Q0', 'Q1', 'Q2'])
    expected = {(str(t), a) for t in metadata['task_ids'] for a in arms}
    keys = [(str(r['task_id']), r['arm']) for r in rows]
    assert metadata['status'] == 'completed', 'incomplete run'
    assert len(keys) == len(set(keys)) and set(keys) == expected, 'missing or duplicate result'
    for row in rows:
        assert all(k in row for k in ('subset', 'pool', 'family_id', 'usage', 'final', 'elapsed_seconds'))
        assert row['subset'] == 'PLT' and row['workflow_arm'] == 'P7'
        assert row['final'] == row['attempts'][-1], 'final is not actual last attempt'
        assert 1 <= len(row['attempts']) <= 2
        assert not (len(row['attempts']) > 1 and row['attempts'][0]['joint']), 'failed early stop'
        for attempt in row['attempts']:
            assert all(isinstance(attempt[k], bool) for k in ('functional', 'security', 'joint', 'measured'))
            evidence = attempt.get('validation', {}).get('evidence', {})
            assert attempt['functional'] == (evidence.get('functional', {}).get('status') == 'pass')
            assert attempt['security'] == (evidence.get('security', {}).get('status') == 'pass')
            assert attempt['joint'] == (attempt['measured'] and attempt['functional'] and attempt['security'])
    stored = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    recomputed = summarize(rows, 'Q0' if stage == 'learn' else 'Q1')
    assert all(stored[k] == recomputed[k] for k in ('arms', 'paired')), 'remote statistics mismatch'
    cost = json.loads((directory/'cost.json').read_text(encoding='utf-8'))
    shared = cost['llm']['by_label']['shared_initial.pipeline'] if metadata['args'].get('shared_initial') else {}
    assert sum(r['usage']['calls'] for r in rows) + shared.get('calls', 0) == cost['llm']['total']['calls'], 'LLM calls mismatch'
    assert sum(r['usage']['total_tokens'] for r in rows) + shared.get('total_tokens', 0) == cost['llm']['total']['total_tokens'], 'LLM token mismatch'
    if metadata['args'].get('shared_initial'):
        prepared = {str(r['task_id']): r for r in read_rows(directory/'shared_initial.jsonl')}
        assert set(prepared) == {str(t) for t in metadata['task_ids']}
        assert shared['calls'] == len(prepared), 'shared calls must be counted once per task'
        for row in rows:
            assert row['attempts'][0]['generation']['initial_analysis'] == prepared[str(row['task_id'])]['initial_analysis']
    events = read_rows(directory/'memory_q_events.jsonl')
    by_task = {str(r['task_id']): r for r in rows}
    if stage == 'compare':
        assert not events and metadata['q_unchanged'], 'evaluation fed back to Q'
    else:
        before = {n['invariant_id']: n for n in read_rows(directory/'input_memory.jsonl')}
        after = {n['invariant_id']: n for n in read_rows(directory/'frozen/m_star_q.jsonl')}
        for event in events:
            attempt = by_task[str(event['task_id'])]['attempts'][event['attempt']]
            adopted = {c['invariant_id'] for c in attempt.get('generation', {}).get('cards', [])}
            identity = event['invariant_id']
            if identity is None:
                assert not adopted, 'missing adoption attribution'
                continue
            assert identity in adopted and event['pool'] == 'D_grow', 'reward on unadopted card'
            node = before[identity]
            assert abs(node.get('q_value', 0)-event['q_before']) < 1e-12
            if event['reward'] is not None:
                assert event['reward'] in (-1, 1)
                node['q_value'] = event['q_before'] + metadata['args']['alpha']*(event['reward']-event['q_before'])
                node['q_visits'] = node.get('q_visits', 0) + 1
            assert abs(node.get('q_value', 0)-event['q_after']) < 1e-12
        assert before == after, 'Q event replay does not reconstruct frozen memory'
    return {'stage': stage, 'rows': len(rows), 'tasks': len(metadata['task_ids']),
            'families': len({r['family_id'] for r in rows}), 'schema': metadata['output_schema_version'],
            'native_statistics_recomputed': True, 'calls_and_tokens_matched': True,
            'q_event_attribution_checked': True, 'status': 'pass'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    report = {'learn': check_run(args.root/'learn'), 'compare': check_run(args.root/'compare')}
    learn_ids = {str(r['family_id']) for r in read_rows(args.root/'learn/rows.jsonl')}
    gate_ids = {str(r['family_id']) for r in read_rows(args.root/'compare/rows.jsonl')}
    assert not learn_ids & gate_ids, 'learning/evaluation family overlap'
    report['learning_evaluation_families_disjoint'] = True
    write_json_atomic(args.root/'format_check.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
