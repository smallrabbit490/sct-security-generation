"""B03R仅生成提醒与c0共享前缀；注入请求回调，不创建网络客户端或读取凭据。

复用原P7/原验证器。E/K各自记录首次终选、复析和规划；同层第二条件精确复用，
到首次生成才分叉。修复轮独立。不写经验或Q，不提供付费启动入口。
"""
from __future__ import annotations

import copy
import json

from configs.cle_v41_migration_20261025.binding_study import binding_suffix, TARGET_STAGES
from configs.cle_v41_migration_20261025.run import empty_provider
from methods.cle_ablation import runner
from methods.sct_trajectory.context_pipeline import analysis_prompt
from methods.sct_trajectory.replay_journal import ReplayStop


SETTINGS = {'model': 'deepseek-v4.1-flash-1017', 'max_tokens': 4096,
            'thinking': 'disabled', 'temperature': 0, 'roles': ['user'], 'stream': True}
GENERATION = TARGET_STAGES[-1]


def request_input(prompt):
    """只记录非认证设置；原SelectorPrompt仍原样交给原客户端，保留256预算/期限。"""
    selector = type(prompt).__name__ == 'SelectorPrompt'
    return {'prompt': str(prompt), 'settings': copy.deepcopy(SETTINGS),
            'selector': selector, 'effective_max_tokens': 256 if selector else 4096}


def native_selector(nodes, embedding):
    """接入原A7 semantic_llm终选0–3卡；调用方提供冻结节点与原向量客户端。"""
    def select(query, request):
        from methods.sct_trajectory.ablation import get_config
        from methods.sct_trajectory.hsk_tree import HskTree
        from methods.sct_trajectory.retriever import HskTreeRetriever
        retriever = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=embedding, semantic_delta=None,
            lambda_q=0.5, candidate_order=None)
        cards = retriever.search(query, limit=3, pool_nodes=nodes)
        return cards, retriever.last_hier_trace
    return select


class SharedPrefix:
    """一个重复×有无卡层的精确响应前缀；未封口/分歧时停，不能静默再请求。

    retrieval事件内嵌原终选请求，第二条件直接复用其结果，避免二次选卡。
    保存回调在请求前后及生成边界执行；中断现场与成功前缀不能混用。
    """
    def __init__(self, identity, save, record=None, review=None):
        self.identity, self.save = identity, save
        self.review = review
        self.record = copy.deepcopy(record) if record is not None else {
            'prefix_id': identity, 'status': 'new', 'events': []}

    def persist(self):
        self.save('shared_prefixes/' + self.identity, copy.deepcopy(self.record))

    def session(self, arm, request, select, protocol):
        if self.record['status'] not in ('new', 'sealed'):
            raise ReplayStop('incomplete_shared_prefix_no_new_dispatch')
        producer = self.record['status'] == 'new'
        if producer:
            self.record.update(status='recording', producer_arm=arm)
            self.persist()
        return PrefixSession(self, arm, request, select, protocol, producer)


class PrefixSession:
    """只替换生成末尾提醒；共同绑定保护沿用旧三阶段薄包装。"""
    def __init__(self, prefix, arm, request, select, protocol, producer):
        self.prefix, self.arm, self.source, self.select = prefix, arm, request, select
        self.reminder = protocol[protocol['arms'][arm]['generation_reminder'] + '_reminder']
        self.producer, self.before_generation, self.cursor = producer, True, 0
        self.nested = None
        self.branch_events = []
        self.branch_key = 'branches/' + prefix.identity.rsplit('_', 1)[0] + '_' + arm

    def persist(self):
        self.prefix.persist()
        self.prefix.save(self.branch_key, copy.deepcopy(self.branch_events))

    def _source_request(self, prompt, target, reference):
        event = {'kind': 'request', 'input': request_input(prompt), 'status': 'prepared',
                 'origin': 'source', 'reference': reference}
        target.append(event)
        self.persist()
        try:
            event['response'] = copy.deepcopy(self.source(prompt))
            event['status'] = 'completed'
        except BaseException as exc:
            event.update(status='failed_or_unresolved', error_type=type(exc).__name__)
            self.persist()
            raise ReplayStop('source_request_incomplete_no_new_dispatch') from exc
        if target is not self.branch_events:
            self.branch_events.append({'kind': 'request', 'origin': 'source', 'reference': reference})
        self.persist()
        return copy.deepcopy(event['response'])

    def _consume(self, kind, value):
        events = self.prefix.record['events']
        if self.cursor >= len(events):
            raise ReplayStop('shared_prefix_missing_event_no_new_dispatch')
        event = events[self.cursor]
        if event['kind'] != kind or event['input'] != value or event['status'] != 'completed':
            raise ReplayStop('shared_prefix_input_mismatch_no_new_dispatch')
        self.cursor += 1
        self.branch_events.append({'kind': kind, 'origin': 'shared_prefix', 'status': 'reused',
                                   'reference': f'{self.prefix.identity}/events/{self.cursor - 1}'})
        self.persist()
        return copy.deepcopy(event)

    def request(self, prompt):
        text = str(prompt)
        generation = text.startswith(GENERATION)
        if text.startswith(TARGET_STAGES):
            prompt = text + binding_suffix('VALID_SIGNATURES')
        if generation:
            # 边界比较的是完整生成输入，含原题/分析/采用卡/计划；提醒随后才追加。
            if self.before_generation:
                identity = request_input(prompt)
                if self.producer:
                    self.prefix.record.update(status='sealed', generation_input=identity,
                        plan_relation_review='pending_review_not_used_to_filter_prefix')
                    self.persist()
                    if self.prefix.review is not None:
                        self.prefix.record['plan_relation_review'] = self.prefix.review(copy.deepcopy(self.prefix.record))
                        self.persist()
                elif (self.cursor != len(self.prefix.record['events']) or
                      self.prefix.record['generation_input'] != identity):
                    raise ReplayStop('shared_generation_input_mismatch_no_new_dispatch')
                self.before_generation = False
            prompt = str(prompt) + '\n' + self.reminder
        if not self.before_generation:
            return self._source_request(prompt, self.branch_events,
                                        f'{self.branch_key}/events/{len(self.branch_events)}')
        if self.nested is not None:
            reference = f'{self.prefix.identity}/events/{len(self.prefix.record["events"]) - 1}'
            return self._source_request(prompt, self.nested, reference + f'/requests/{len(self.nested)}')
        if self.producer:
            return self._source_request(prompt, self.prefix.record['events'],
                                        f'{self.prefix.identity}/events/{len(self.prefix.record["events"])}')
        return self._consume('request', request_input(prompt))['response']

    def provider(self, query):
        if self.before_generation and not self.producer:
            return self._consume('retrieval', query)['result']
        event = {'kind': 'retrieval', 'input': copy.deepcopy(query), 'status': 'prepared', 'requests': []}
        target = self.prefix.record['events'] if self.before_generation else self.branch_events
        target.append(event)
        self.persist()
        self.nested = event['requests'] if self.before_generation else None
        try:
            result = empty_provider(query) if self.arm.startswith('E_') else self.select(query, self.request)
            event.update(status='completed', result=copy.deepcopy(result))
        except BaseException as exc:
            event.update(status='failed_or_unresolved', error_type=type(exc).__name__)
            self.persist()
            raise ReplayStop('retrieval_incomplete_no_new_dispatch') from exc
        finally:
            self.nested = None
        self.persist()
        return copy.deepcopy(result)

    def finish(self):
        if self.before_generation:
            raise ReplayStop('prefix_did_not_reach_generation')


def run_repeat(task, cells, *, protocol, request_for, select, save, review_prefix=None, on_row=None):
    """按冻结顺序执行一个重复；请求/落盘均由调用方注入，默认无任何付费路径。

    返回原生P7行及共享记录。row.usage含共享响应的逻辑消费，不可相加作实付用量；
    物理HTTP/Token仍必须从原请求日志去重核算。此函数不实现授权/时段/预算启动器。
    """
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.english_policy import assert_english_text
    repeat = cells[0]['repeat']
    if (len(cells) != 4 or {c['arm'] for c in cells} != set(protocol['arms']) or
            any(c['repeat'] != repeat or c['task_id'] != str(task['index']) for c in cells)):
        raise ReplayStop('repeat_requires_four_distinct_frozen_cells')
    pair_id = f"{task['index']}_r{repeat}"
    initial_prompt = analysis_prompt(runner.plt_contract(task))
    initial_record = {'input': request_input(initial_prompt), 'status': 'prepared'}
    save('shared_initial/' + pair_id, copy.deepcopy(initial_record))
    try:
        response = request_for('shared_initial_' + pair_id)(initial_prompt)
    except BaseException as exc:
        initial_record.update(status='failed_or_unresolved', error_type=type(exc).__name__)
        save('shared_initial/' + pair_id, copy.deepcopy(initial_record))
        raise ReplayStop('shared_initial_incomplete_no_new_dispatch') from exc
    initial_record.update(status='completed', response=copy.deepcopy(response))
    try:
        initial = _extract_json(_content(response))
        assert isinstance(initial, dict) and all(isinstance(initial.get(k), list) and initial[k]
            for k in ('vulnerability_hypothesis', 'functional_invariants'))
        assert_english_text(json.dumps(initial, ensure_ascii=False), context='initial_analysis')
        error = None
    except Exception as exc:
        initial, error = {'unmeasured': True}, type(exc).__name__
    initial_record.update(parsed=initial, parse_error=error)
    save('shared_initial/' + pair_id, copy.deepcopy(initial_record))
    prefixes = {kind: SharedPrefix(pair_id + '_' + kind, save, review=review_prefix) for kind in ('E', 'K')}
    rows = []
    for cell in cells:
        arm = cell['arm']
        session = prefixes[arm[0]].session(arm, request_for(cell['cell_id']), select, protocol)
        row = runner.run_one('PLT', task, 'P7', session.request, {'full': []},
            initial_analysis=copy.deepcopy(initial), max_experiences=3, retrieval_mode='semantic_llm',
            candidate_order=None, delta=None, retrieval_provider=session.provider)
        session.finish()
        row.update(relation_arm=arm, repeat=repeat, cell_id=cell['cell_id'], family_id=task['family_id'],
                   protocol=protocol['protocol'], shared_prefix_id=session.prefix.identity,
                   Q_updates=0, card_generation=0)
        save('task_rows/' + cell['cell_id'], row)
        rows.append(row)
        if on_row is not None:
            on_row(row)
    return {'rows': rows, 'initial': initial_record,
            'prefixes': {kind: copy.deepcopy(p.record) for kind, p in prefixes.items()}}
