"""设计阶段的流程图契约；检查结构与信息边界，不评分、不写长期经验库。"""
from __future__ import annotations

OPERATIONS = {'llm', 'memory', 'inspect', 'select', 'branch', 'repeat', 'finish'}
PUBLIC_INPUTS = {'public_task', 'contract', 'memory_bank', 'public_suite'}
FORBIDDEN = {'official_score', 'ground_truth', 'unit_test', 'test_code', 'reference_answer',
             'hidden_tests', 'D_gate', 'H_pass', 'Base', 'Plus'}


def validate_graph(graph, inside_repeat=False):
    """输入模型提案→错误列表；节点及边必须可执行，禁止解题路径消费官方反馈。

    属于提案质量门控，不证明方法有效；未知操作、非法引用、循环、不可达终点
    均拒绝。repeat的子图独立校验；禁止循环藏在普通边里。不修改长期库。
    """
    errors = []
    if not isinstance(graph, dict) or not isinstance(graph.get('nodes'), list) or not isinstance(graph.get('edges'), list):
        return ['invalid_graph_schema']
    nodes = graph['nodes']
    ids = [n.get('id') for n in nodes if isinstance(n, dict)]
    if len(ids) != len(nodes) or any(not isinstance(i, str) or not i for i in ids):
        return ['invalid_node_id']
    if len(set(ids)) != len(ids):
        errors.append('duplicate_node_id')
    if set(ids) & (PUBLIC_INPUTS | FORBIDDEN | {'iteration_candidate'}):
        errors.append('reserved_node_id')
    outgoing = {i: [] for i in ids}
    incoming = {i: [] for i in ids}
    for edge in graph['edges']:
        if not isinstance(edge, dict) or not isinstance(edge.get('source'),str) or not isinstance(edge.get('target'),str) or edge.get('source') not in outgoing or edge.get('target') not in incoming:
            errors.append('dangling_edge')
            continue
        outgoing[edge['source']].append(edge['target'])
        incoming[edge['target']].append(edge['source'])
        if edge.get('condition') not in (None, 'always', 'problem', 'clean'):
            errors.append('unsupported_edge_condition')
        condition_source = edge.get('condition_source', edge['source'])
        if not isinstance(condition_source, str) or condition_source not in outgoing:
            errors.append('invalid_condition_source')
        elif condition_source != edge['source'] and condition_source not in incoming[edge['target']]:
            errors.append('condition_source_without_edge:' + edge['target'] + ':' + condition_source)
    for node in nodes:
        if not isinstance(node.get('operation'),str) or node.get('operation') not in OPERATIONS:
            errors.append('unknown_operation:' + node['id'])
        inputs = node.get('inputs', [])
        if not isinstance(inputs, list) or any(not isinstance(x, str) for x in inputs):
            errors.append('invalid_inputs:' + node['id'])
            continue
        for ref in inputs:
            if ref in FORBIDDEN or any(part in FORBIDDEN for part in ref.split('.')):
                errors.append('forbidden_input:' + ref)
            elif ref not in PUBLIC_INPUTS and ref not in ids and ref != 'iteration_candidate':
                errors.append('unknown_input:' + ref)
            elif ref in ids and ref not in incoming[node['id']]:
                errors.append('input_without_edge:' + node['id'] + ':' + ref)
            if ref == 'iteration_candidate' and not inside_repeat:
                errors.append('iteration_input_outside_repeat')
        optional = node.get('optional_inputs', [])
        if not isinstance(optional, list) or any(ref not in inputs for ref in optional):
            errors.append('invalid_optional_inputs:' + node['id'])
        if node.get('operation') == 'repeat':
            errors.extend('repeat:' + e for e in validate_graph(node.get('graph'), inside_repeat=True))
        if node.get('operation') == 'inspect' and ('contract' not in inputs or not any(ref in ids or ref=='iteration_candidate' for ref in inputs)):
            errors.append('inspection_requires_candidate_and_contract:' + node['id'])
        if node.get('operation') == 'memory' and not {'public_task','memory_bank'} <= set(inputs):
            errors.append('memory_requires_task_and_bank:' + node['id'])
    remaining = {k: len(v) for k, v in incoming.items()}
    queue = [i for i in ids if remaining[i] == 0]
    order = []
    while queue:
        item = queue.pop(0)
        order.append(item)
        for nxt in outgoing[item]:
            remaining[nxt] -= 1
            if remaining[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(ids):
        errors.append('cycle_requires_repeat')
    finishes = [n['id'] for n in nodes if n.get('operation') == 'finish']
    if len(finishes) != 1:
        errors.append('exactly_one_finish_required')
    elif len(nodes) > 1 and not incoming[finishes[0]]:
        errors.append('unreachable_finish')
    if finishes and outgoing[finishes[0]]:
        errors.append('finish_has_outgoing_edge')
    if len(finishes) == 1:
        # finish 最终只能收到一个候选；多条互斥/可选路径可由运行时检查，
        # 真正同时收到多个候选时，执行器会拒绝并要求先经过 select。
        finish_node = next(n for n in nodes if n.get('id') == finishes[0])
        finish_inputs = finish_node.get('inputs', [])
        finish_optional = finish_node.get('optional_inputs', [])
        if isinstance(finish_inputs, list) and len(finish_inputs) > 1 and not finish_optional:
            errors.append('finish_requires_explicit_selection:' + finishes[0])
        reachable = {finishes[0]}
        work = [finishes[0]]
        while work:
            for predecessor in incoming[work.pop()]:
                if predecessor not in reachable:
                    reachable.add(predecessor)
                    work.append(predecessor)
        errors.extend('dead_node:' + i for i in ids if i not in reachable)
    return errors


def topological_nodes(graph, inside_repeat=False):
    """执行前按边排序；输入已校验图，输出确定顺序，无模型/评分/库更新。"""
    errors = validate_graph(graph, inside_repeat=inside_repeat)
    if errors:
        raise ValueError(';'.join(errors))
    result = []
    done = set()
    pending = list(graph['nodes'])
    while pending:
        for node in list(pending):
            dependencies = {e['source'] for e in graph['edges'] if e['target'] == node['id']}
            if dependencies <= done:
                result.append(node)
                done.add(node['id'])
                pending.remove(node)
    return result
