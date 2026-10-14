"""解题阶段通用图执行器：按图组织操作，隔离官方反馈，记录实际节点路径。"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import time
from .schemas import PUBLIC_INPUTS, topological_nodes


def stamp():
    return datetime.now(timezone.utc).isoformat()


def has_problem(value):
    """只检查公开结构/断言证据；缺测不是已确认问题。"""
    return bool(value.get('issues')) or any(c.get('status') == 'fail' and c.get('measured')
                                          for c in value.get('checks', {}).get('cases', []))


def safe_error_code(exc):
    """把受控异常映射为网页可读错误码；不保存可能含提示词或密钥的异常原文。"""
    message = str(exc)
    known = {
        'model_output_truncated': 'model_output_truncated',
        'all_output_capacities_truncated': 'model_output_truncated',
        'no_json_object': 'model_response_not_json',
        'json_not_object': 'model_response_not_json',
        'empty_model_content': 'model_response_empty',
        'invalid_api_response': 'model_response_invalid',
        'no_final_candidate': 'no_final_candidate',
        'finish_requires_explicit_selection': 'finish_requires_explicit_selection',
        'repeat_requires_exactly_one_candidate': 'repeat_requires_one_candidate',
    }
    return known.get(message, 'unknown_error')


class GraphExecutor:
    """输入合法流程图与公开上下文→候选/事件；操作通过注入绑定，不读取答案。

    信息引用必须由图声明。结构、缺少输入、操作错误分别记录，所有模型节点
    均不能写长期库。官方评分不在此执行器可见上下文中。
    """
    def __init__(self, operators, on_event=None, timeout=600):
        self.operators = operators
        self.on_event = on_event
        self.timeout = timeout

    def run(self, graph, context, inside_repeat=False):
        order = topological_nodes(graph, inside_repeat=inside_repeat)
        values = {k: v for k, v in context.items() if k in PUBLIC_INPUTS or (inside_repeat and k == 'iteration_candidate')}
        events, candidates = [], []
        failed_nodes = set()
        emitted_count = 0
        selected_code = ''
        start = time.monotonic()
        def emit_live(event):
            nonlocal emitted_count
            emitted_count += 1
            event = {**event, 'event_id': str(emitted_count)}
            if self.on_event:
                self.on_event(event)
        def emit_terminal(event):
            nonlocal emitted_count
            emitted_count += 1
            event = {**event, 'event_id': str(emitted_count)}
            events.append(event)
            if self.on_event:
                self.on_event(event)
        for node in order:
            event = {'node_id': node['id'], 'operation': node['operation'],
                     'started_at': stamp(), 'input_refs': node.get('inputs', [])}
            emit_live({**event, 'status': 'running'})
            edges = [e for e in graph['edges'] if e['target'] == node['id']]
            # 同一来源同时声明条件边和普通边时，条件边优先，避免普通边绕过分支。
            # 不同来源则彼此独立；任一来源路径有效即可激活汇合节点。
            effective_edges = []
            edges_by_source = {}
            for edge in edges:
                edges_by_source.setdefault(edge['source'], []).append(edge)
            for source_edges in edges_by_source.values():
                guarded = [e for e in source_edges
                           if e.get('condition', 'always') in ('problem', 'clean')]
                effective_edges.extend(guarded or source_edges)
            def active(edge):
                condition_source = edge.get('condition_source', edge['source'])
                if edge['source'] not in values or condition_source not in values:
                    return False
                condition = edge.get('condition', 'always')
                problem = has_problem(values[condition_source])
                return condition in (None, 'always') or (condition == 'problem' and problem) or (condition == 'clean' and not problem)
            activation = effective_edges
            if activation and not any(active(e) for e in activation):
                event.update(status='skipped', reason='branch_not_taken', ended_at=stamp())
                emit_terminal(event)
                continue
            if time.monotonic()-start > self.timeout:
                event.update(status='failed', error_type='workflow_timeout', ended_at=stamp())
                event['ended_at'] = stamp()
                emit_terminal(event)
                break
            def delivered(ref):
                if ref not in values:
                    return False
                information_edges = [e for e in effective_edges if e['source'] == ref]
                if not information_edges:
                    return True
                return any(active(e) for e in information_edges)
            inputs = {ref: values[ref] for ref in node.get('inputs', []) if delivered(ref)}
            missing = [ref for ref in node.get('inputs', []) if not delivered(ref)]
            required_missing = [ref for ref in missing if ref not in node.get('optional_inputs', [])]
            if required_missing:
                failed_sources = [ref for ref in required_missing if ref in failed_nodes]
                if failed_sources:
                    event.update(status='skipped', reason='upstream_node_failed',
                                 missing_refs=missing, upstream_failed_refs=failed_sources, ended_at=stamp())
                else:
                    event.update(status='failed', error_type='missing_inputs', error_code='missing_inputs',
                                 missing_refs=missing, ended_at=stamp())
                    failed_nodes.add(node['id'])
                emit_terminal(event)
                continue
            try:
                if node['operation'] == 'finish':
                    choices = [v for v in inputs.values() if isinstance(v, dict) and v.get('code')]
                    unique = {}
                    for choice in choices:
                        digest = hashlib.sha256(choice['code'].encode()).hexdigest()
                        unique.setdefault(digest, choice)
                    choices = list(unique.values())
                    if not choices:
                        raise ValueError('no_final_candidate')
                    if len(choices)!=1:
                        raise ValueError('finish_requires_explicit_selection')
                    output = choices[-1]
                    selected_code = output['code']
                elif node['operation'] == 'branch':
                    evidence = next((v for v in reversed(list(inputs.values())) if isinstance(v, dict) and ('issues' in v or 'checks' in v)), None)
                    if evidence is None:
                        raise ValueError('branch_requires_public_inspection')
                    output = {**evidence, 'branch_decision':'problem' if has_problem(evidence) else 'clean',
                              'branch_policy':'confirmed_public_problem_only'}
                elif node['operation'] == 'repeat':
                    output = self.repeat(node, inputs)
                else:
                    if node['operation'] not in self.operators:
                        raise ValueError('unbound_operation:' + node['operation'])
                    output = self.operators[node['operation']](node, inputs)
                if not isinstance(output, dict):
                    raise ValueError('operator_output_not_object')
                values[node['id']] = output
                if output.get('code'):
                    digest = hashlib.sha256(output['code'].encode()).hexdigest()
                    if not any(c['sha256'] == digest for c in candidates):
                        candidates.append({'code': output['code'], 'sha256': digest, 'node_id': node['id']})
                    event['code_sha256'] = digest
                event.update(status='completed', output=output, ended_at=stamp())
            except Exception as exc:
                event.update(status='failed', error_type=type(exc).__name__,
                             error_code=safe_error_code(exc), ended_at=stamp())
                failed_nodes.add(node['id'])
                # 异常原文可能含输入或密钥；只保存类别。操作自己的受控错误可另存。
            emit_terminal(event)
        for event in events:
            for nested in event.get('output', {}).get('repeat_rounds', []):
                for candidate in nested['candidates']:
                    if not any(c['sha256'] == candidate['sha256'] for c in candidates):
                        candidates.append(candidate)
        return {'selected_code': selected_code, 'events': events, 'candidates': candidates,
                'workflow_completed': bool(selected_code), 'elapsed_seconds': time.monotonic()-start}

    def repeat(self, node, inputs):
        """显式重复子图，重复输出/证据停滞/超时终止；不设低调用配额，不评分。"""
        choices = [v for v in inputs.values() if isinstance(v, dict) and v.get('code')]
        if len(choices)>1:
            raise ValueError('repeat_requires_exactly_one_candidate')
        candidate = choices[0] if choices else {}
        memories=[v['memory'] for v in inputs.values() if isinstance(v,dict) and 'memory' in v]
        if candidate and memories:
            candidate={**candidate,'training_memory':memories[-1]}
        context = {k: v for k,v in inputs.items() if k in PUBLIC_INPUTS}
        seen = {hashlib.sha256(candidate['code'].encode()).hexdigest()} if candidate.get('code') else set()
        rounds = []
        started = time.monotonic()
        while time.monotonic()-started < self.timeout:
            if candidate and not has_problem(candidate) and node.get('only_on_problem', True):
                return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'no_confirmed_public_problem'}
            context['iteration_candidate'] = candidate
            round_number=len(rounds)+1
            def child_event(event):
                if self.on_event:
                    self.on_event({**event,'parent_node_id':node['id'],'round':round_number,
                                   'event_id':f"{node['id']}.{round_number}.{event['event_id']}"})
            nested = GraphExecutor(self.operators, on_event=child_event, timeout=self.timeout-(time.monotonic()-started)).run(node['graph'], context, inside_repeat=True)
            rounds.append(nested)
            if not nested['selected_code']:
                return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'child_no_final_candidate'}
            digest = hashlib.sha256(nested['selected_code'].encode()).hexdigest()
            if digest in seen:
                return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'repeated_candidate'}
            seen.add(digest)
            after = next(e['output'] for e in reversed(nested['events']) if e.get('operation') == 'finish' and e.get('output'))
            if candidate and has_problem(candidate):
                from methods.a7_exploration.protocol import improves
                if not improves(candidate, after):
                    return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'no_improvement_or_public_regression'}
            if memories:
                after = {**after, 'training_memory': memories[-1]}
            candidate = after
            if len(rounds) > 1 and json.dumps(candidate, sort_keys=True) == json.dumps(context['iteration_candidate'], sort_keys=True):
                return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'no_new_evidence'}
        return {**candidate, 'repeat_rounds': rounds, 'stop_reason': 'workflow_timeout'}
