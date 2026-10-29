"""有界准备两题真实探针的共享初析/原CLE选卡；不生成代码，不更新Q。

当前用户目标授权按任务包推进。本入口只准备1394/102各两次独立初析与选择，
保存已返回响应和共享输入，五条件后续复用；技术错误即停，不重发已落盘步骤。
"""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from configs.cle_memory_mechanisms_20261023.prepare import CONFIG, ROOT, OUT, ONLINE, read, write
from methods.cle_ablation import runner
from methods.sct_trajectory.agent_pipeline import _content, _extract_json
from methods.sct_trajectory.context_pipeline import analysis_prompt
from methods.sct_trajectory.english_policy import assert_english_text
from methods.sct_trajectory.hsk_tree import HskTree
from methods.sct_trajectory.retriever import HskTreeRetriever
from methods.sct_trajectory.ablation import get_config


def prepare_starts(tasks, nodes, requester, embedding, out, identifiers):
    """公开题面进入初析，完整公开查询进入原选择器；每个重复独立产生一次。"""
    completed = []
    for repeat in (1, 2):
        for tid in identifiers:
            contract = runner.plt_contract(tasks[tid])
            response = requester(analysis_prompt(contract))
            initial = _extract_json(_content(response))
            if not isinstance(initial, dict) or not all(isinstance(initial.get(k), list) and initial[k]
                for k in ['vulnerability_hypothesis', 'functional_invariants']):
                raise ValueError('initial_analysis_incomplete')
            assert_english_text(json.dumps(initial, ensure_ascii=False), context='initial_analysis')
            query = {**contract, 'threat_analysis': initial, 'current_code': '', 'failure_evidence': {}}
            retriever = HskTreeRetriever(HskTree(), requester=requester, ablation=get_config('A7'),
                retrieval_mode='semantic_llm', embedding_client=embedding, semantic_delta=-1,
                lambda_q=.5, candidate_order=None)
            cards = retriever.search(query, limit=3, pool_nodes=nodes)
            trace = retriever.last_hier_trace
            if not trace or trace['status'] != 'completed':
                raise ValueError('selection_not_completed')
            assert len(cards) <= 3
            item = {'task_id': tid, 'repeat': repeat, 'public_contract': contract,
                'initial_analysis': initial, 'query': query, 'selected_cards': cards,
                'retrieval_trace': trace, 'initial_response_usage': response.get('usage'),
                'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
                'model_generated_code': False, 'Q_updates': 0}
            write(out / 'shared_starts' / f'{tid}_r{repeat}.json', item)
            completed.append({'task_id': tid, 'repeat': repeat,
                'candidates': len(trace['candidate_ids']), 'selected_ids': [c['invariant_id'] for c in cards]})
            write(out / 'completed_starts.json', completed)
            print(json.dumps({'shared_starts_completed': len(completed), **completed[-1]}, ensure_ascii=False), flush=True)
    return completed


def main():
    protocol = read(CONFIG / 'view_protocol.json')
    model = protocol['model']
    authorization = protocol['shared_start_execution']
    if not authorization['enabled'] or authorization['scope'] != 'two_task_shared_starts_only':
        raise ValueError('shared_start_stage_not_enabled')
    identifiers = read(CONFIG / 'manifest.json')['technical_probe_ids']
    assert identifiers == authorization['task_ids'] == ['1394', '102']
    references = read(OUT / 'v2/reference_preflight.json')
    assert all(r['passed'] for r in references['records'] if r['task_id'] in identifiers)
    tasks = {str(t['index']): t for t in read(OUT / 'v2/tasks_train.json')}
    destination = OUT / protocol['shared_start_run']
    destination.mkdir(exist_ok=False)
    meta = {'protocol': protocol['protocol'] + '-shared-starts', 'status': 'running',
        'authorization': authorization, 'model': model, 'thinking': 'disabled',
        'temperature': 0, 'max_tokens': 4096, 'selector_max_tokens': 256,
        'embedding_model': 'text-embedding-3-large', 'retrieval_mode': 'semantic_llm',
        'candidate_order': None, 'delta': -1, 'lambda_q_unused_for_original_order': .5,
        'max_experiences': 3, 'task_ids': identifiers, 'repeats': 2,
        'planned_shared_starts': 4, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'code_generation_started': False, 'Q_updates': 0}
    write(destination / 'run_metadata.json', meta)
    from methods.cle_ablation.run_joint_contract import RequestBudget, bounded_embedding_client
    from methods.sct_trajectory.run_closed_loop import _requester
    budget = RequestBudget(authorization['max_http_attempts'], authorization['max_conservative_tokens'],
                           authorization['max_embedding_attempts'])
    native = _requester(model, 60, max_tokens=4096, max_inflight=1, thinking='disabled')
    bounded = budget.wrap(native, 4096)
    requests = destination / 'requests'
    requests.mkdir()
    count = 0
    def requester(prompt):
        nonlocal count
        count += 1
        stem = requests / f'{count:04d}'
        write(stem.with_suffix('.status.json'), {'status': 'submitted',
              'submitted_utc': datetime.now(timezone.utc).isoformat()})
        stem.with_suffix('.prompt.txt').write_text(str(prompt), encoding='utf-8')
        try:
            response = bounded(prompt)
            write(stem.with_suffix('.response.json'), response)
            write(stem.with_suffix('.status.json'), {'status': 'returned'})
            return response
        except Exception as exc:
            write(stem.with_suffix('.status.json'), {'status': 'failed', 'error_type': type(exc).__name__,
                'diagnostics': getattr(exc, 'diagnostics', [])})
            raise
        finally:
            write(destination / 'cost.json', budget.snapshot())
    embedding = bounded_embedding_client(budget, ROOT / 'translation_work/cache/embeddings/cle.sqlite3')
    nodes = runner.load_memory(ONLINE / 'D_grow/frozen/m_star_q.jsonl')
    try:
        completed = prepare_starts(tasks, nodes, requester, embedding, destination, identifiers)
    except Exception as exc:
        meta.update(status='stopped_technical_error', error_type=type(exc).__name__,
                    request_diagnostics=getattr(exc, 'diagnostics', []))
        write(destination / 'run_metadata.json', meta)
        write(destination / 'cost.json', budget.snapshot())
        print(json.dumps({'status': meta['status'], 'error_type': meta['error_type'],
                          'completed_starts': len(read(destination / 'completed_starts.json'))
                          if (destination / 'completed_starts.json').exists() else 0}, ensure_ascii=False), flush=True)
        raise SystemExit(1)
    meta.update(status='completed_shared_starts_waiting_view_review', completed_starts=len(completed),
                completed_utc=datetime.now(timezone.utc).isoformat())
    write(destination / 'run_metadata.json', meta)
    write(destination / 'cost.json', budget.snapshot())
    print(json.dumps({'status': meta['status'], 'completed_starts': len(completed),
        'cost': {k: v for k, v in budget.snapshot().items() if k != 'records'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
