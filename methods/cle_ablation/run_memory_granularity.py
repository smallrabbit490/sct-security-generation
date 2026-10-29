"""C02固定20/120/480格分阶段入口；默认零API，技术门和C1决定扩大范围。"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from . import runner
from .granularity_execution import run_cells, save
from .granularity_results import make_schedule, execution_gate, PHASE_LIMITS
from .memory_granularity_study import GranularityProvider
from .memory_view_study import CONFIG, RAW, ONLINE, read
from methods.sct_trajectory.provider_policy import CURRENT_MODEL


def readiness(protocol, control, phase='technical'):
    """只检查本阶段实际所需门，不把人审和Notion原件设为两题技术门。"""
    reasons = []
    execution = protocol[phase + '_execution']
    if not protocol['paid_execution_enabled'] or not execution['enabled']:
        reasons.append('paid_execution_disabled')
    if not protocol['consumer_frozen'] or not protocol['consumer_version']:
        reasons.append('consumer_not_frozen')
    caps = ('max_http_attempts', 'max_conservative_tokens', 'max_embedding_attempts')
    if any(type(execution.get(k)) is not int or execution[k] < 1 for k in caps):
        reasons.append('C02_independent_budget_missing')
    if protocol['authorized_C02_HTTP_budget'] != execution.get('max_http_attempts'):
        reasons.append('C02_budget_scope_mismatch')
    if execution['scope'] != f'{phase}_{PHASE_LIMITS[phase]}' or execution['planned_P7'] != PHASE_LIMITS[phase]:
        reasons.append('scope_must_be_fixed_' + f'{phase}_{PHASE_LIMITS[phase]}')
    if (control.get('status') != 'passed' or control.get('model') != CURRENT_MODEL
            or len(control.get('controls', [])) < 2
            or not all(c.get('passed') is True for c in control.get('controls', []))):
        reasons.append('provider_code_controls_not_passed')
    expected = {'model': CURRENT_MODEL, 'thinking': 'disabled', 'temperature': 0,
        'max_tokens': 4096, 'embedding_model': 'text-embedding-3-large',
        'Q_used_or_updated': False, 'max_selected_cards': 3, 'delta': -1,
        'candidate_order': None, 'max_repairs': 1, 'delivery': 'last_attempt_first_joint_early_stop'}
    if protocol['unchanged'] != expected:
        reasons.append('original_CLE_execution_parameters_changed')
    return reasons


def inputs():
    """复用四份已付费共享起点及两卡静态材料，不重新初析、选卡或生成绑定。"""
    shared = RAW / read(CONFIG / 'view_protocol.json')['shared_start_run']
    if read(shared / 'run_metadata.json')['model'] != CURRENT_MODEL:
        raise ValueError('shared_start_model_mismatch')
    from configs.cle_memory_mechanisms_20261023.prepare_granularity_views import load_materials
    specs, bindings, examples = load_materials()
    tasks = {str(t['index']): t for t in read(RAW / 'v2/tasks_train.json')}
    starts, materials = {}, {}
    for path in sorted((shared / 'shared_starts').glob('*.json')):
        start = read(path)
        starts[start['task_id'], start['repeat']] = start
    for tid in tasks:
        materials[tid] = lambda cards, contract, level, tid=tid: {
            'card_specs': specs, 'bindings': bindings.get(tid, {}), 'examples': examples}
    return tasks, starts, materials


def prepare_shared_start(task, repeat, journal, retrieve):
    """只用公开题面生成一次初析/原CLE选卡，作为该题重复下五档的共同起点。"""
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.context_pipeline import analysis_prompt
    from methods.sct_trajectory.english_policy import assert_english_text
    contract = runner.plt_contract(task)
    response = journal.request(analysis_prompt(contract))
    initial = _extract_json(_content(response))
    if not isinstance(initial, dict) or not all(isinstance(initial.get(k), list) and initial[k]
            for k in ('vulnerability_hypothesis', 'functional_invariants')):
        raise ValueError('shared_initial_analysis_incomplete')
    assert_english_text(json.dumps(initial, ensure_ascii=False), context='initial_analysis')
    query = {**contract, 'threat_analysis': initial, 'current_code': '', 'failure_evidence': {}}
    cards, trace = journal.retrieve(query, retrieve)
    if len(cards) > 3:
        raise ValueError('shared_selection_exceeds_three_cards')
    return {'task_id': contract['task_id'], 'repeat': repeat, 'public_contract': contract,
        'initial_analysis': initial, 'query': query, 'selected_cards': cards,
        'retrieval_trace': trace, 'initial_response_usage': response.get('usage'),
        'model_generated_code': False, 'Q_updates': 0}


def clients():
    """门通过之后才创建同模型客户端；向量也通过当前格记账，不额外重试。"""
    from .provider_adaptation import STREAM_TRANSPORT
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.ablation import get_config
    transport = STREAM_TRANSPORT
    request = _requester(CURRENT_MODEL, transport['socket_timeout'], max_tokens=4096,
        max_inflight=1, thinking='disabled', hard_timeout=transport['hard_timeout'],
        gate_wait_timeout=transport['gate_wait_timeout'], max_attempts=1, stream=True)

    class JournalEmbedding(EmbeddingClient):
        journal = None

        def _request(self, texts):
            def perform():
                before = self.usage
                vectors = super(JournalEmbedding, self)._request(texts)
                after = self.usage
                missing = after['usage_missing_calls'] > before['usage_missing_calls']
                usage = None if missing else {k: after[k] - before[k] for k in ('prompt_tokens', 'total_tokens')}
                return {'vectors': vectors, 'usage': usage, 'model': self.model}
            return self.journal.embedding(texts, perform)['vectors']

    embedding = JournalEmbedding(model='text-embedding-3-large',
        cache_path=runner.ROOT / 'translation_work/cache/embeddings/cle.sqlite3',
        key_loader=load_key, timeout=60)
    nodes = runner.load_memory(ONLINE / 'D_grow/frozen/m_star_q.jsonl')

    def retrieve(query, journal):
        embedding.journal = journal
        retriever = HskTreeRetriever(HskTree(), requester=journal.request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=embedding, semantic_delta=-1,
            lambda_q=.5, candidate_order=None)
        cards = retriever.search(query, limit=3, pool_nodes=nodes)
        return cards, retriever.last_hier_trace
    return request, retrieve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--phase', choices=list(PHASE_LIMITS), default='technical')
    parser.add_argument('--resume', action='store_true', help='仅原目录断点，不重启技术失败或未决请求')
    parser.add_argument('--out', type=Path, help='运行区新目录；resume时为已保存目录')
    args = parser.parse_args(argv)
    protocol = read(CONFIG / 'granularity_protocol.json')
    control = read(RAW / protocol['provider_control_summary'])
    reasons = readiness(protocol, control, args.phase)
    cells = make_schedule(read(CONFIG / 'manifest.json'), protocol['schedule_seed'])
    saved_rows = []
    if args.out:
        for cell in cells:
            path = args.out / 'task_rows' / f'{cell["cell_id"]}.json'
            if path.exists(): saved_rows.append(read(path))
    stage = execution_gate(cells, saved_rows, args.phase, native_protocol=protocol['native_protocol'])
    reasons.extend(stage['reasons'])
    if args.phase != 'technical':
        issues = read(CONFIG / 'known_contract_issues.json')['issues']
        if any(i['task_id'] in protocol['unresolved_contract_task_ids']
               and i['status'].startswith('unresolved') for i in issues):
            reasons.append('pilot_public_contract_unresolved')
    report = {'protocol': protocol['native_protocol'], 'scope': f'{args.phase}_{stage["prefix_limit"]}',
        'model': protocol['unchanged']['model'],
        'planned_P7': stage['prefix_limit'], 'scheduled_total': len(cells),
        'stage_gate': stage, 'ready': not reasons, 'reasons': reasons,
        'new_API_calls': 0, 'Q_updates': 0}
    if not args.run:
        print(json.dumps(report, ensure_ascii=False))
        return report
    if reasons:
        raise ValueError('C02_paid_execution_not_ready:' + ','.join(reasons))
    if args.out is None:
        parser.error('--run必须提供--out，不自动覆盖既有结果')
    if not args.out.resolve().is_relative_to(RAW.resolve()):
        raise ValueError('C02_output_must_be_in_ignored_run_directory')
    tasks, starts, materials = inputs()
    for cell in cells[:stage['prefix_limit']]:
        tid, repeat = cell['task_id'], cell['repeat']
        if (tid, repeat) not in starts:
            continue  # 新题的共享准备在启用后的同一预算内逐题完成，缺材料即停止。
        start = starts[tid, repeat]
        if runner.plt_contract(tasks[tid]) != start['public_contract']:
            raise ValueError('shared_public_contract_changed')
        GranularityProvider(start, cell['memory_level'], None, materials[tid], tasks[tid]['family_id'])
    memory = ONLINE / 'D_grow/frozen/m_star_q.jsonl'
    frozen = runner.digest(memory)
    sources = ['methods/cle_ablation/granularity_execution.py',
        'methods/cle_ablation/run_memory_granularity.py', 'methods/cle_ablation/memory_granularity_study.py',
        'methods/cle_ablation/granularity_results.py',
        'methods/sct_trajectory/memory_granularity.py', 'methods/sct_trajectory/context_pipeline.py',
        'methods/cle_ablation/runner.py', 'methods/sct_trajectory/run_closed_loop.py',
        'methods/sct_trajectory/retriever.py', 'methods/sct_trajectory/semantic_retrieval.py',
        'methods/cle_ablation/provider_adaptation.py', 'methods/cle_ablation/run_joint_contract.py']
    sources.append('methods/sct_trajectory/provider_policy.py')
    runtime = {'consumer_version': protocol['consumer_version'], 'unchanged': protocol['unchanged'],
        'git_branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=runner.ROOT, text=True).strip(),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runner.ROOT, text=True).strip(),
        'memory': str(memory), 'memory_sha256': frozen,
        'source_sha256': {p: runner.digest(runner.ROOT / p) for p in sources},
        'shared_starts': str(RAW / read(CONFIG / 'view_protocol.json')['shared_start_run'] / 'shared_starts'),
        'shared_start_cost_separate': str(RAW / read(CONFIG / 'view_protocol.json')['shared_start_run'] / 'cost.json'),
        'material_preparation': 'existing static reviewed materials; zero new model binding calls'}
    request, retrieve = clients()
    try:
        return run_cells(cells, tasks, starts, materials, request, retrieve,
            protocol[args.phase + '_execution'], args.out, resume=args.resume,
            preparation_cost_complete=True, is_experiment_score=True, runtime_metadata=runtime,
            stop_after=stage['prefix_limit'], phase=args.phase, prepare_start=prepare_shared_start)
    finally:
        metadata_path = args.out / 'run_metadata.json'
        if metadata_path.exists():
            metadata = read(metadata_path)
            metadata['memory_unchanged'] = runner.digest(memory) == frozen
            if not metadata['memory_unchanged']:
                metadata['status'] = 'stopped_frozen_memory_changed'
            save(metadata_path, metadata)


if __name__ == '__main__':
    main()
