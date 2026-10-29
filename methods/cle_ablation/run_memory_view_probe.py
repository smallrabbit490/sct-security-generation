"""B02两题、五条件、两重复的原P7技术探针。

只复用已保存首次初析/选卡；修复继续原P7检索和反馈。来源分区缺失时等待
Agent审核原文，不退化成空卡或重发付费步骤。代码、验证、请求及费用均落盘，Q不更新。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from methods.cle_ablation import runner
from methods.cle_ablation.memory_view_study import CONFIG, RAW, ONLINE, read, write
from methods.cle_ablation.run_joint_contract import RequestBudget, bounded_embedding_client
from methods.sct_trajectory.ablation import get_config
from methods.sct_trajectory.hsk_tree import HskTree
from methods.sct_trajectory.memory_views import MODES, apply_memory_view, draft_view, source_projection
from methods.sct_trajectory.retriever import HskTreeRetriever
from methods.sct_trajectory.provider_policy import CURRENT_MODEL, MODEL_REVISION
from methods.cle_ablation.provider_adaptation import (
    TRANSPORT, STREAM_TRANSPORT, carried_budget, exact_saved_response, normalize_structured_response)

VERSION = 'cle-memory-view-two-task-P7-v1'


def now():
    return datetime.now(timezone.utc).isoformat()


def schedule(identifiers, repeats=2, seed=20261023):
    """成绩产生前固定题×重复内的条件顺序，不按结果换题。"""
    rng, result = random.Random(seed), []
    for repeat in range(1, repeats + 1):
        for tid in identifiers:
            modes = list(MODES)
            rng.shuffle(modes)
            result.extend({'task_id': tid, 'repeat': repeat, 'view_arm': m,
                           'cell_id': f'{tid}_r{repeat}_{m}'} for m in modes)
    return result


class ViewProvider:
    """首次消费同一公开起点；修复按本臂当前代码重新召回，不借用其他臂结果。"""
    def __init__(self, start, mode, retrieve, specifications):
        self.start, self.mode = start, mode
        self.retrieve, self.specifications = retrieve, specifications
        self.calls = 0

    def __call__(self, query):
        self.calls += 1
        if self.calls == 1:
            if query != self.start['query']:
                raise ValueError('first_query_differs_from_shared_start')
            cards = copy.deepcopy(self.start['selected_cards'])
            trace = copy.deepcopy(self.start['retrieval_trace'])
            trace['shared_first_selection'] = True
        elif self.mode == 'B0':
            cards, trace = [], {'status': 'completed', 'candidate_ids': [], 'selected_ids': [],
                                'reason': 'B0_memory_disabled_in_repair'}
        else:
            cards, trace = self.retrieve(query)
            if trace.get('status') != 'completed':
                raise ValueError('repair_selection_not_completed')
        if len(cards) > 3:
            raise ValueError('original_CLE_card_cap_exceeded')
        original_ids = [c['invariant_id'] for c in cards]
        specs = self.specifications(cards) if self.mode != 'B0' else {}
        cards = apply_memory_view(cards, self.mode, specs)
        trace.update(view_arm=self.mode, pre_view_selected_ids=original_ids,
                     selected_ids=[c['invariant_id'] for c in cards])
        return cards, trace


def await_source_review(cards, registry, out, cell):
    """付费选卡完成后保留原件等待来源分区，不自动签署人类适用性标签。"""
    needed = {c['invariant_id'] for c in cards}
    specs = read(registry)
    missing = needed - specs.keys()
    if not missing:
        return specs
    destination = out / 'pending_views' / cell
    destination.mkdir(parents=True, exist_ok=True)
    for card in cards:
        if card['invariant_id'] in missing:
            write(destination / (card['invariant_id'] + '.json'),
                  {'source': source_projection(card), 'draft': draft_view(card)})
    write(out / 'runtime_status.json', {'status': 'waiting_source_content_review',
          'cell_id': cell, 'card_ids': sorted(missing), 'registry': str(registry), 'time': now()})
    print(json.dumps({'needs_source_review': sorted(missing), 'cell_id': cell}, ensure_ascii=False), flush=True)
    while missing:
        time.sleep(1)
        specs = read(registry)
        missing = needed - specs.keys()
    # render_view验证字符覆盖及角色，registry有ID不等于合法审核完成。
    apply_memory_view(cards, 'BFS', specs)
    write(out / 'runtime_status.json', {'status': 'running', 'cell_id': cell, 'time': now()})
    return specs


def technical_errors(row):
    """正常F/S失败保留为成绩；格式/请求/缺测问题停止后续付费题。"""
    errors = []
    for attempt in row['attempts']:
        if not attempt.get('measured'):
            errors.append(attempt.get('error_type') or 'validation_unmeasured')
        generation = attempt.get('generation', {})
        if generation.get('error_type'):
            errors.append(generation['error_type'])
        if generation and not generation.get('workflow_completed'):
            errors.append('workflow_incomplete')
    return errors


def summary(rows, planned, protocol=VERSION):
    """只汇总真实原生交付；两题技术样本不判断12题收益门。"""
    result = {'protocol': protocol, 'planned_P7': planned, 'completed_P7': len(rows),
              'Q_updates': 0, 'effectiveness_gate_evaluated': False, 'arms': {}}
    for mode in MODES:
        items = [r for r in rows if r['view_arm'] == mode]
        counts = {}
        for name, position in [('first', 0), ('final', -1)]:
            attempts = [r['attempts'][position] for r in items]
            counts[name] = {k: sum(bool(a.get('measured')) and bool(a.get(k)) for a in attempts)
                            for k in ['functional', 'security', 'joint']}
            counts[name]['measured'] = sum(bool(a.get('measured')) for a in attempts)
        result['arms'][mode] = {'completed': len(items), **counts,
            'unmeasured': sum(not r['attempts'][-1].get('measured') for r in items),
            'technical_errors': sum(bool(technical_errors(r)) for r in items),
            'repairs': sum(len(r['attempts']) == 2 for r in items)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--provider-adaptation', action='store_true',
                        help='显式使用v2统一中转适配，必须先通过两个小任务控制')
    parser.add_argument('--stream',action='store_true',help='配合provider-adaptation使用v3流式适配')
    args = parser.parse_args()
    protocol = read(CONFIG / 'view_protocol.json')
    model = protocol['model']
    if model != CURRENT_MODEL:
        raise ValueError('current_model_protocol_mismatch')
    execution = protocol['two_task_P7_execution']
    adapted = args.provider_adaptation
    if args.stream and not adapted:
        raise ValueError('stream_requires_explicit_provider_adaptation')
    adaptation_key = 'provider_adaptation_v3_stream' if args.stream else 'provider_adaptation_v2'
    control_dir = 'B02_provider_adaptation_v3_stream' if args.stream else 'B02_provider_adaptation_v2'
    version = ('cle-memory-view-two-task-P7-v3-stream' if args.stream else
               'cle-memory-view-two-task-P7-v2' if adapted else VERSION)
    version += '-' + MODEL_REVISION
    transport = STREAM_TRANSPORT if args.stream else TRANSPORT
    enabled = protocol[adaptation_key]['enabled'] if adapted else execution['enabled']
    identifiers = read(CONFIG / 'manifest.json')['technical_probe_ids']
    assert identifiers == execution['task_ids'] == ['1394', '102']
    cells = schedule(identifiers)
    if not args.run:
        print(json.dumps({'protocol': version, 'planned_P7': len(cells), 'API_calls': 0,
                          'enabled': enabled, 'scope': execution['scope'], 'model': model}, ensure_ascii=False))
        return
    if not enabled or execution['scope'] != 'two_task_P7_only':
        raise ValueError('two_task_P7_not_enabled')
    if adapted:
        control = read(RAW / control_dir / 'summary.json')
        if control['status'] != 'passed' or control['model'] != model:
            raise ValueError('provider_small_task_controls_not_passed_for_current_model')
    shared = RAW / protocol['shared_start_run']
    if read(shared / 'run_metadata.json')['model'] != model:
        raise ValueError('shared_start_model_mismatch')
    # 新目录避免覆盖、重复启动；进程若中断不自动重跑未决请求。
    out = RAW / (('B02_two_task_P7_v3_stream' if args.stream else
                 'B02_two_task_P7_v2' if adapted else 'B02_two_task_P7_v1') + '_' + MODEL_REVISION)
    out.mkdir(exist_ok=False)
    tasks = {str(t['index']): t for t in read(RAW / 'v2/tasks_train.json')}
    starts = {(tid, rep): read(shared / 'shared_starts' / f'{tid}_r{rep}.json')
              for tid in identifiers for rep in (1, 2)}
    registry = out / 'reviewed_views.json'
    specs = read(RAW / 'B01/reviewed_probe_views.json')
    specs.update(read(shared / 'reviewed_views.json'))
    write(registry, specs)
    # 任一首次卡缺审核时，先在免费边界停止，不先提交模型请求。
    for start in starts.values():
        for mode in MODES:
            apply_memory_view(start['selected_cards'], mode, specs)
        assert start['public_contract'] == runner.plt_contract(tasks[start['task_id']])
    memory_path = ONLINE / 'D_grow/frozen/m_star_q.jsonl'
    memory_before = runner.digest(memory_path)
    nodes = runner.load_memory(memory_path)
    meta = {'protocol': version, 'status': 'running', 'pid': os.getpid(), 'created_utc': now(),
        'model': model, 'thinking': 'disabled', 'temperature': 0, 'max_tokens': 4096,
        'embedding_model': 'text-embedding-3-large', 'delta': -1, 'candidate_order': None,
        'max_experiences': 3, 'repairs': 1, 'delivery': 'last_attempt_first_joint_early_stop',
        'planned_P7': len(cells), 'task_ids': identifiers, 'repeats': 2, 'execution': execution,
        'shared_starts': str(shared), 'memory': str(memory_path), 'memory_sha256': memory_before,
        'Q_updates': 0, 'code_generation_started': False,
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runner.ROOT,text=True).strip(),
        'git_branch': subprocess.check_output(['git', 'branch', '--show-current'],cwd=runner.ROOT,text=True).strip()}
    if adapted:
        meta.update(provider_adaptation=protocol[adaptation_key],transport=transport,
            prior_failed_protocol=str(RAW / 'B02_two_task_P7_v1'),
            prior_fault_count=1, prior_fault_in_method_comparison=False,
            budget_includes_prior_fault_and_controls=True)
    write(out / 'run_metadata.json', meta)
    write(out / 'schedule.json', cells)
    (out / 'source').mkdir()
    for source in [Path(__file__), runner.ROOT / 'methods/sct_trajectory/memory_views.py',
                   runner.ROOT / 'methods/sct_trajectory/context_pipeline.py', Path(runner.__file__),
                   runner.ROOT / 'methods/cle_ablation/provider_adaptation.py',
                   runner.ROOT / 'methods/cle_ablation/run_joint_contract.py',
                   runner.ROOT / 'methods/sct_trajectory/provider_policy.py',
                   runner.ROOT / 'methods/sct_trajectory/run_closed_loop.py']:
        shutil.copyfile(source, out / 'source' / source.name)
    from methods.sct_trajectory.run_closed_loop import _requester
    budget = (carried_budget(execution,[read(RAW / control_dir / 'cost.json')]) if adapted
              else RequestBudget(execution['max_http_attempts'],execution['max_conservative_tokens'],
                                 execution['max_embedding_attempts']))
    if adapted:
        native = _requester(model,transport['socket_timeout'],max_tokens=4096,
            max_inflight=1,thinking='disabled',hard_timeout=transport['hard_timeout'],
            gate_wait_timeout=transport['gate_wait_timeout'],max_attempts=1,stream=args.stream)
    else:
        native = _requester(model,60,max_tokens=4096,max_inflight=1,thinking='disabled')
    def journal_native(prompt):
        # wrap已预留预算；网络调用之前保存，未返回请求的费用不能消失。
        write(out / 'cost.json',budget.snapshot())
        return native(prompt)
    bounded = budget.wrap(journal_native,4096,max_attempts=1 if adapted else 3)
    embedding = bounded_embedding_client(budget,runner.ROOT / 'translation_work/cache/embeddings/cle.sqlite3')
    requests = out / 'requests'
    requests.mkdir()
    count, rows = 0, []
    current = {}

    def requester(prompt):
        nonlocal count
        count += 1
        stem = requests / f'{count:04d}'
        write(stem.with_suffix('.status.json'), {'status': 'submitted', 'cell_id': current['cell_id'],
              'submitted_utc': now()})
        stem.with_suffix('.prompt.txt').write_text(str(prompt),encoding='utf-8')
        before = len(budget.records)
        try:
            response, reused = (exact_saved_response(prompt,RAW / 'B02_two_task_P7_v1',current['cell_id'])
                                if adapted and read(RAW / 'B02_two_task_P7_v1/run_metadata.json')['model'] == model
                                else (None,None))
            if response is None:
                response = bounded(prompt)
            write(stem.with_suffix('.response.json'),response)
            delivered,note=normalize_structured_response(prompt,response) if adapted else (response,None)
            if note:
                write(stem.with_suffix('.normalized_response.json'),delivered)
                write(stem.with_suffix('.normalization.json'),note)
            write(stem.with_suffix('.status.json'),{'status':'reused' if reused else 'returned',
                'cell_id':current['cell_id'],'returned_utc':now(),'reused_from':reused,
                'normalization':note})
            return delivered
        except Exception as exc:
            write(stem.with_suffix('.status.json'),{'status':'failed','cell_id':current['cell_id'],
                'error_type':type(exc).__name__,'time':now()})
            raise
        finally:
            for record in budget.records[before:]:
                record.setdefault('cell_id',current['cell_id'])
                record['source_protocol']=version
            write(out / 'cost.json',budget.snapshot())

    def retrieve(query):
        before = len(budget.records)
        retriever = HskTreeRetriever(HskTree(),requester=requester,ablation=get_config('A7'),
            retrieval_mode='semantic_llm',embedding_client=embedding,semantic_delta=-1,
            lambda_q=.5,candidate_order=None)
        try:
            cards = retriever.search(query,limit=3,pool_nodes=nodes)
            return cards,retriever.last_hier_trace
        finally:
            for record in budget.records[before:]:
                record.setdefault('cell_id',current['cell_id'])
                record['source_protocol']=version
            write(out / 'cost.json',budget.snapshot())

    for current in cells:
        tid, repeat, mode = current['task_id'],current['repeat'],current['view_arm']
        write(out / 'runtime_status.json',{'status':'running',**current,'time':now()})
        provider = ViewProvider(starts[tid,repeat],mode,retrieve,
            lambda cards: await_source_review(cards,registry,out,current['cell_id']))
        meta['code_generation_started'] = True
        row = runner.run_one('PLT',tasks[tid],'P7',requester,{'full':nodes},embedding,
            retrieval_mode='semantic_llm',delta=-1,lambda_q=.5,max_experiences=3,
            candidate_order=None,initial_analysis=copy.deepcopy(starts[tid,repeat]['initial_analysis']),
            retrieval_provider=provider)
        row.update(**current,protocol=version,final=row['attempts'][-1],Q_updates=0)
        write(out / 'task_rows' / f"{current['cell_id']}.json",row)
        for i,attempt in enumerate(row['attempts']):
            write(out / 'attempts' / current['cell_id'] / f'{i}.json',attempt)
        with (out / 'rows.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        rows.append(row)
        write(out / 'summary.json',summary(rows,len(cells),version))
        write(out / 'cost.json',budget.snapshot())
        meta.update(completed_P7=len(rows),last_completed_cell=current['cell_id'])
        errors = technical_errors(row)
        print(json.dumps({'completed_P7':len(rows),'planned_P7':len(cells),**current,
            'final':{k:row['final'].get(k) for k in ['measured','functional','security','joint']},
            'technical_errors':errors,'known_tokens':budget.snapshot()['known_returned_tokens']},ensure_ascii=False),flush=True)
        if errors:
            meta.update(status='stopped_technical_error',technical_errors=errors)
            break
        write(out / 'run_metadata.json',meta)
    else:
        meta.update(status='completed_technical_probe')
    meta.update(finished_utc=now(),memory_unchanged=runner.digest(memory_path)==memory_before)
    if not meta['memory_unchanged']:
        meta['status'] = 'stopped_frozen_memory_changed'
    write(out / 'run_metadata.json',meta)
    write(out / 'runtime_status.json',{'status':meta['status'],'completed_P7':len(rows),'time':now()})
    write(out / 'cost.json',budget.snapshot())
    print(json.dumps({'status':meta['status'],'completed_P7':len(rows),'memory_unchanged':meta['memory_unchanged']},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
