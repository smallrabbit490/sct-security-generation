"""功能/安全视图的离线准备与原P7接线探针，不提供付费启动动作。

prepare导出锁定12题的历史候选卡和待审视图；offline-probe仅使用两张已审分区卡，
模型回复为明确标记的离线控制回复。使用目标参考作验证器正向控制，不形成模型成绩。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from methods.cle_ablation import runner
from methods.sct_trajectory.hsk_tree import HskTree
from methods.sct_trajectory.retriever import HskTreeRetriever
from methods.sct_trajectory.memory_views import MODES, apply_memory_view, draft_view, source_projection

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'configs/cle_memory_mechanisms_20261023'
RAW = ROOT / 'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'
OUT = RAW / 'B01'
ONLINE = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def history():
    pilot = set(read(CONFIG / 'manifest.json')['first_pilot_ids'])
    records = {}
    with (ONLINE / 'D_grow/rows.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if str(row['task_id']) in pilot:
                first = row['attempts'][0]
                records[str(row['task_id'])] = {
                    'candidate_ids': first['retrieval_trace']['candidate_ids'],
                    'example_card': (first['generation']['retrieved_cards'][0]
                                     if first['generation']['retrieved_cards'] else None)}
    assert set(records) == pilot
    return records


def prepare_views():
    """仅导出卡片事实，不把历史Q2选择当成新实验的Q0选卡结果。"""
    OUT.mkdir(exist_ok=False)
    hist = history()
    memory = {n.invariant_id: n for n in runner.load_memory(ONLINE / 'D_grow/frozen/m_star_q.jsonl')}
    candidate_ids = sorted({i for row in hist.values() for i in row['candidate_ids']})
    retriever = HskTreeRetriever(HskTree())
    cards = [retriever._to_card({'language': 'python'}, memory[i], base=0, llm=None) for i in candidate_ids]
    with (OUT / 'card_sources.jsonl').open('w', encoding='utf-8') as sources, (OUT / 'view_drafts.jsonl').open('w', encoding='utf-8') as drafts:
        for card in cards:
            sources.write(json.dumps(source_projection(card), ensure_ascii=False) + '\n')
            drafts.write(json.dumps(draft_view(card), ensure_ascii=False) + '\n')
    write(OUT / 'historical_candidate_index.json', {i: {'candidate_ids': r['candidate_ids']} for i, r in hist.items()})
    summary = {'purpose': 'offline annotation sources; not a new retrieval or model result',
        'pilot_tasks': 12, 'unique_candidate_cards': len(cards), 'drafts_pending': len(cards),
        'source': 'historical online Q2 first queries, card bodies from latest frozen snapshot',
        'new_Q0_selection_done': False, 'API_calls': 0, 'Q_updates': 0}
    write(OUT / 'prepare_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def example_spec(card, tid):
    """两张实际卡的事实分区，供接线控制，不表示建议适用性已得到验证。"""
    spec = draft_view(card)
    source = source_projection(card)
    segments = []
    for item in spec['segments']:
        path = item['path']
        field = path[0]
        if field in ('high_level_invariant', 'negative_guardrail'):
            segments.append({**item, 'role': 'functional'})
        elif field in ('applicability', 'language_leaf'):
            segments.append({**item, 'role': 'context'})
        elif field == 'root_cause':
            text = source[field]
            first = text.index('The reason')
            segments.append({**item, 'end': first, 'role': 'context'})
            if tid == '1394':
                split = text.index('3) Verifying')
                segments.extend([{**item, 'start': first, 'end': split, 'role': 'security'},
                                 {**item, 'start': split, 'role': 'functional'}])
            else:
                segments.append({**item, 'start': first, 'role': 'security'})
        elif field == 'fix_directive':
            text = source[field]
            if tid == '1394':
                split = text.index('4) Verify')
                segments.extend([{**item, 'end': split, 'role': 'security'},
                                 {**item, 'start': split, 'role': 'functional'}])
            else:
                start = text.index(', and do not alter')
                end = text.index(' Decoding exceptions')
                segments.extend([{**item, 'end': start, 'role': 'security'},
                                 {**item, 'start': start, 'end': end, 'role': 'functional'},
                                 {**item, 'start': end, 'role': 'security'}])
        else:
            raise ValueError('example partition requires content review: ' + str(path))
    spec.update(review_status='reviewed', segments=segments,
        review_note='Agent content partition for offline wiring; no correctness or target applicability endorsement',
        reviewer='Codex', scope='offline-control-only')
    return spec


def offline_probe():
    """复用真实1394/102题和原P7两次尝试规则；无在线模型，结果不得计入B02。"""
    if (OUT / 'offline_probe_summary.json').exists():
        raise FileExistsError('offline probe already exists; preserve evidence')
    hist = history()
    tasks = {str(t['index']): t for t in read(RAW / 'v2/tasks_train.json')}
    all_results, specifications = [], {}
    for tid in read(CONFIG / 'manifest.json')['technical_probe_ids']:
        task = tasks[tid]
        card = hist[tid]['example_card']
        spec = example_spec(card, tid)
        specifications[card['invariant_id']] = spec
        initial = {'vulnerability_hypothesis': ['Input processing risk under the public contract.'],
                   'functional_invariants': ['Preserve the public interface and valid input behavior.']}
        gt = task['ground_truth']
        reference = gt['code_before'] + gt['patched_code'] + gt['code_after']
        name = task['task_description']['function_name']
        bad = f'def {name}(**kwargs):\n    return None\n'
        for mode in MODES:
            emitted = iter([bad, reference])
            provider_queries, prompts = [], []
            def requester(prompt):
                prompts.append(prompt)
                if prompt.startswith('Generate complete'):
                    content = next(emitted)
                elif prompt.startswith('Plan'):
                    content = json.dumps({'Preserved_Func': 'Preserve public behavior', 'Patch_Scope': 'Implement the interface'})
                else:
                    content = json.dumps({**initial, 'applied_experience_ids': [] if mode == 'B0' else [card['invariant_id']]})
                return {'choices': [{'message': {'content': content}}],
                        'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
            def provider(query):
                provider_queries.append(query)
                cards = apply_memory_view([card], mode, specifications)
                return cards, {'offline_control': True, 'selected_ids': [c['invariant_id'] for c in cards]}
            row = runner.run_one('PLT', task, 'P7', requester, {'full': []},
                                 retrieval_provider=provider, initial_analysis=initial)
            assert len(row['attempts']) == 2
            assert row['attempts'][0]['joint'] is False and row['attempts'][-1]['joint'] is True
            assert row['attempts'][-1]['code'] == reference.strip()
            assert len(provider_queries) == 2
            if mode == 'B0':
                assert all(not a['generation']['cards'] for a in row['attempts'])
            row.update(purpose='offline wiring control, target reference used as synthetic reply',
                       not_an_experiment_score=True, API_calls=0)
            write(OUT / 'offline_probe' / f'{tid}_{mode}.json', row)
            all_results.append({'task_id': tid, 'mode': mode, 'attempts': 2,
                'final_reference_control_pass': True, 'model_generated': False})
    write(OUT / 'reviewed_example_views.json', specifications)
    summary = {'scope': 'offline wiring only; no real LLM/P7 study scores',
        'tasks': 2, 'conditions': 5, 'completed_controls': len(all_results),
        'reference_used_in_stub_only': True, 'API_calls': 0, 'model_tokens': 0, 'Q_updates': 0,
        'original_P7_repair_once_and_last_delivery_verified': True,
        'B0_empty_in_both_attempts': True, 'records': all_results,
        'unreviewed_other_views_block_real_study': True}
    write(OUT / 'offline_probe_summary.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare-views', 'offline-probe'])
    action = parser.parse_args().action
    {'prepare-views': prepare_views, 'offline-probe': offline_probe}[action]()


if __name__ == '__main__':
    main()
