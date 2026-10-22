"""D_init补充Q学习：固定卡库、原P7三张上限，一份轨迹分别计算全反馈与跨题族Q。

这是明确授权的新训练协议。旧D_grow学习器及D_gate/Base/Plus只读边界保持原样。
prepare/preflight/report不调用API；probe/learn是显式付费入口，不自动启动。
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

from configs.cle_q_coverage_learning_20261019.qualification import bindings, placeholder_paths
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.run_memory_q_full import sources
from methods.cle_ablation.run_memory_q_gate_q0 import account_request, frozen_runner
from methods.cle_ablation.run_memory_q_unlimited import DATASET, FAMILIES, FIELDS, POOLS, inputs
from methods.cle_ablation.runner import load_memory
from methods.sct_trajectory.memory_q import reward_from_evidence, update_q
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest, stratified_tasks
from methods.sct_trajectory.run_memory_q_study import _write_memory

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'configs/cle_memory_q_dinit_20261019'
OUT = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/dinit_learning_v1'
CURATED = ROOT / 'results/curated/cle_memory_q_dinit_20261019'
PARENT = ROOT / 'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
MEMORY = PARENT / 'observe/frozen/m_star_q.jsonl'
PROTOCOL = 'cle-q-dinit-observer-cap3-v1'
POLICIES = ('all_feedback', 'cross_family')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    """按物理行读原生JSONL，保留正文中合法的Unicode行分隔符。"""
    if not Path(path).exists():
        return []
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def jsonl(path, values):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(''.join(json.dumps(v, ensure_ascii=False) + '\n' for v in values), encoding='utf-8')


def csv_file(path, values):
    if not values:
        return
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def body(nodes):
    return [{k: v for k, v in n.to_dict().items() if k not in {'q_value', 'q_visits'}} for n in nodes]


def card_origins(nodes, tasks, pools):
    """主来源及可追溯合并来源均参与跨族判断；无法还原的合并来源不猜测。"""
    membership = {str(i): pool for pool, ids in pools.items() for i in ids}
    by_id = {n.invariant_id: n.to_dict() for n in nodes}
    result = {}
    for node in nodes:
        source = node.to_dict().get('source', {})
        identifier = str(source.get('task_id'))
        pending, visited, source_tasks, unresolved = [node.invariant_id], set(), set(), set()
        while pending:
            card_id = pending.pop()
            if card_id in visited:
                continue
            visited.add(card_id)
            if card_id not in by_id:
                unresolved.add(card_id)
                continue
            item = by_id[card_id].get('source', {})
            task_id = str(item.get('task_id'))
            if task_id in tasks:
                source_tasks.add(task_id)
            else:
                unresolved.add(card_id)
            pending.extend(item.get('absorbed_from', []))
        result[node.invariant_id] = {
            'source_task_id': identifier if identifier in tasks else None,
            'source_pool': membership.get(identifier, 'unknown'),
            'source_family': tasks[identifier]['family_id'] if identifier in tasks else None,
            'known_source_tasks': sorted(source_tasks),
            'known_source_families': sorted({tasks[i]['family_id'] for i in source_tasks}),
            'unresolved_absorbed_ids': sorted(unresolved),
        }
    return result


def qualify(task):
    """零API参考执行与公开绑定检查；隐藏内容只留在运行区，不进入生成提示。"""
    from methods.sct_trajectory.closed_loop import validate_and_state
    ground = task['ground_truth']
    evidence, state = validate_and_state(task, ground['code_before'] + ground['patched_code'] + ground['code_after'], timeout=20)
    paths = placeholder_paths(task)
    undeclared, parse_error = bindings(task)
    reasons = []
    if state != 'A':
        reasons.append('reference_not_joint')
    if paths:
        reasons.append('placeholder_in_task')
    if undeclared:
        reasons.append('undeclared_public_binding')
    if parse_error:
        reasons.append('reference_or_setup_parse_error')
    return {'task_id': str(task['index']), 'family_id': task['family_id'], 'cwe': str(task['CWE_ID']),
            'reference_state': state, 'reference_evidence': evidence, 'placeholder_paths': paths,
            'undeclared_setup_bindings': undeclared, 'parse_error': parse_error,
            'reward_eligible': not reasons, 'exclusion_reasons': reasons}


def prepare():
    """冻结原始输入与源码，先清点卡片来源；绝不把来源验证成绩直接转换为Q。"""
    if (OUT / 'run_metadata.json').exists():
        verify()
        return read(OUT / 'inventory.json')
    if shutil.disk_usage(ROOT.anchor).free < 3 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    _, tasks, pools = inputs()
    nodes = load_memory(MEMORY)
    origins = card_origins(nodes, tasks, pools)
    families = {pool: {tasks[str(i)]['family_id'] for i in ids} for pool, ids in pools.items()}
    overlap = {a + '|' + b: len(families[a] & families[b])
               for a, b in [('D_init', 'D_grow'), ('D_init', 'D_gate'), ('D_grow', 'D_gate')]}
    if any(overlap.values()):
        raise ValueError('training_evaluation_family_overlap')
    inventory = {'protocol': PROTOCOL, 'cards': len(nodes), 'learned_cards': sum(n.q_visits > 0 for n in nodes),
                 'origin_pools': dict(Counter(o['source_pool'] for o in origins.values())),
                 'origin_tasks': len({o['source_task_id'] for o in origins.values() if o['source_task_id']}),
                 'origin_families': len({o['source_family'] for o in origins.values() if o['source_family']}),
                 'cards_with_unresolved_origins': sum(bool(o['unresolved_absorbed_ids']) for o in origins.values()),
                 'pools': {k: len(v) for k, v in pools.items()}, 'family_overlap': overlap,
                 'Q_baseline': 'M1: prior D_grow unlimited observer, inherited without resetting', 'new_API_calls': 0}
    OUT.mkdir(parents=True, exist_ok=True)
    CONFIG.mkdir(parents=True, exist_ok=True)
    CURATED.mkdir(parents=True, exist_ok=True)
    _write_memory(OUT / 'input_memory.jsonl', nodes)
    write(OUT / 'origins.json', origins)
    write(OUT / 'inventory.json', inventory)
    csv_file(CURATED / 'card_origin_coverage.csv', [
        {'invariant_id': n.invariant_id, 'cwe': n.cwe, **origins[n.invariant_id],
         'q_value': n.q_value, 'q_visits': n.q_visits} for n in nodes])
    paths = list(dict.fromkeys([p for p in sources() if p.name != 'runner.py'] + [
        Path(__file__), CONFIG / 'protocol.json',
        ROOT / 'configs/cle_q_coverage_learning_20261019/qualification.py',
        ROOT / 'methods/cle_ablation/run_memory_q_unlimited.py',
        ROOT / 'methods/cle_ablation/run_memory_q_gate_q0.py',
        ROOT / 'configs/cle_memory_q_unlimited_20261018/public_contract_overrides.json',
        PARENT / 'source_snapshot/methods/cle_ablation/runner.py']))
    identity = {str(p.relative_to(ROOT)): file_digest(p) for p in paths}
    for name in identity:
        destination = OUT / 'source_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    write(OUT / 'run_metadata.json', {
        'protocol': PROTOCOL, 'status': 'prepared_no_API', 'source_identity': identity,
        'input_identity': {str(p.relative_to(ROOT)): file_digest(p) for p in [DATASET, FAMILIES, POOLS, MEMORY]},
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'python': sys.version, 'D_gate_execution': False, 'new_P7_runs': 0})
    return inventory


def verify():
    metadata = read(OUT / 'run_metadata.json')
    for name, expected in {**metadata['source_identity'], **metadata['input_identity']}.items():
        if file_digest(ROOT / name) != expected:
            raise RuntimeError('locked_input_or_source_changed:' + name)
    if [n.to_dict() for n in load_memory(MEMORY)] != [n.to_dict() for n in load_memory(OUT / 'input_memory.jsonl')]:
        raise RuntimeError('input_memory_changed')


def preflight():
    """检查全部303题后一次性锁名单；按CWE轮转/字符串ID取12个不同family，不看新模型成绩。"""
    prepare()
    if (OUT / 'manifest.json').exists():
        return read(OUT / 'manifest.json')
    _, tasks, pools = inputs()
    ordered = [str(t['index']) for t in stratified_tasks([tasks[str(i)] for i in pools['D_init']], 0)]
    controls = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for number, item in enumerate(executor.map(qualify, [tasks[i] for i in ordered]), 1):
            controls[item['task_id']] = item
            write(OUT / 'reference_preflight' / (item['task_id'] + '.json'), item)
            if number % 30 == 0:
                print({'preflight_checked': number, 'total': len(ordered)}, flush=True)
    learning = [i for i in ordered if controls[i]['reward_eligible']]
    probe, used_families = [], set()
    for identifier in learning:
        family = tasks[identifier]['family_id']
        if family not in used_families and len(probe) < 12:
            probe.append(identifier)
            used_families.add(family)
    manifest = {'protocol': PROTOCOL, 'pool': 'D_init', 'all_tasks': ordered, 'learning': learning,
                'task_families': {i: tasks[i]['family_id'] for i in learning},
                'probe': probe, 'qualified': len(learning), 'excluded': len(ordered) - len(learning),
                'preflight_passed': len(probe) == 12, 'maximum_new_P7_runs': len(learning),
                'selection': 'CWE round robin, string task ID, first12 unique inferred families',
                'max_rounds': 1, 'D_gate_execution': False}
    write(OUT / 'qualification.json', {'tasks': list(controls.values()), 'API_calls': 0})
    write(OUT / 'manifest.json', manifest)
    write(CONFIG / 'manifest.json', manifest)
    csv_file(CURATED / 'qualification.csv', [
        {k: (','.join(v) if isinstance(v, list) else v) for k, v in item.items()
         if k not in {'reference_evidence', 'placeholder_paths'}} for item in controls.values()])
    return manifest


def row_issues(row):
    """原P7最多c0/c1、Joint早停、交付末次；失败是停止条件，保留原始成绩。"""
    issues = []
    if row.get('worker_error'):
        return ['worker_error']
    attempts = row.get('attempts', [])
    if not 1 <= len(attempts) <= 2:
        return ['invalid_attempt_count']
    if row.get('final') != attempts[-1] or (len(attempts) == 2 and attempts[0].get('joint')):
        issues.append('P7_delivery_mismatch')
    for attempt in attempts:
        generation = attempt.get('generation', {})
        selected = {c['invariant_id'] for c in generation.get('retrieved_cards', [])}
        adopted = {c['invariant_id'] for c in generation.get('cards', [])}
        if len(selected) > 3 or not adopted <= selected:
            issues.append('selection_contract_failed')
        trace = attempt.get('retrieval_trace') or generation.get('retrieval_trace') or {}
        if trace.get('status') != 'completed':
            issues.append('retrieval_not_completed')
        if not generation.get('workflow_completed'):
            issues.append('workflow_incomplete')
        if not attempt.get('measured'):
            issues.append('F_S_not_measured')
    return sorted(set(issues))


def credit_rows(items, source, origins, manifest, policy):
    """仅授权D_init真实采用的完整测量授信；同轨迹离线回放，不伪装成D_grow。

    all_feedback包括同题族，cross_family只用已知不同题族；均继承M1，不修改原库。
    每次c0/c1分别按原奖励公式更新，不能用参考实现通过或单纯召回来赋Q。
    """
    if policy not in POLICIES:
        raise ValueError('unknown_credit_policy')
    nodes = copy.deepcopy(source)
    by_id = {n.invariant_id: n for n in nodes}
    allowed = set(manifest['learning'])
    events = []
    by_task = {r['task_id']: r for r in items}
    if len(by_task) != len(items):
        raise ValueError('duplicate_task_records')
    if any(r.get('pool') != 'D_init' or r['task_id'] not in allowed for r in items):
        raise ValueError('D_init_only_qualified_learning')
    for identifier in manifest['learning']:
        if identifier not in by_task:
            continue
        row = by_task[identifier]
        if row['family_id'] != manifest['task_families'][identifier]:
            raise ValueError('learning_family_mismatch')
        for attempt in row.get('attempts', []):
            generation = attempt.get('generation', {})
            selected = {c['invariant_id'] for c in generation.get('retrieved_cards', [])}
            adopted = list(dict.fromkeys(c['invariant_id'] for c in generation.get('cards', [])))
            if len(selected) > 3 or not set(adopted) <= selected:
                raise ValueError('invalid_actual_adoption')
            evidence = attempt.get('validation', {}).get('evidence', {})
            reward = reward_from_evidence(evidence, code=attempt.get('code', ''))
            if row.get('worker_error') or not generation.get('workflow_completed'):
                reward = None
            for card_id in adopted or [None]:
                origin = origins[card_id] if card_id else {}
                known_families = origin.get('known_source_families', [])
                relation = ('same_family' if row['family_id'] in known_families else
                            'unknown' if not known_families or origin.get('unresolved_absorbed_ids') else 'cross_family')
                skip = 'no_adopted_experiences' if card_id is None else None
                if card_id and reward is None:
                    skip = 'incomplete_or_technical_measurement'
                if card_id and policy == 'cross_family' and relation != 'cross_family':
                    skip = 'same_or_unknown_origin_family'
                node = by_id[card_id] if card_id else None
                before = node.q_value if node else None
                if node and not skip:
                    node.q_value = update_q(before, reward, .3)
                    node.q_visits += 1
                events.append({'task_id': identifier, 'family_id': row['family_id'], 'pool': 'D_init',
                               'attempt': attempt['attempt'], 'policy': policy, 'invariant_id': card_id,
                               'origin_relation': relation,
                               'same_source_task': identifier in origin.get('known_source_tasks', []),
                               'reward': reward, 'credited': bool(node and not skip), 'skip_reason': skip,
                               'q_before': before, 'q_after': node.q_value if node else None,
                               'q_visits': node.q_visits if node else None, 'protocol': PROTOCOL})
    if body(nodes) != body(source):
        raise RuntimeError('fixed_memory_body_changed')
    old = {n.invariant_id for n in source if n.q_visits}
    learned = {n.invariant_id for n in nodes if n.q_visits}
    return nodes, events, {'policy': policy, 'learned_cards': len(learned), 'new_cards': len(learned - old),
                           'coverage': len(learned) / len(nodes),
                           'new_card_ids': sorted(learned - old),
                           'valid_updates': sum(e['credited'] for e in events),
                           'credited_relations': dict(Counter(e['origin_relation'] for e in events if e['credited']))}


def collect_rows():
    return [read(p) for p in sorted((OUT / 'task_rows').glob('*.json'))]


def report():
    """复算两种授信和成本；没有实际生成记录时Joint写null，不能当0分实验。"""
    verify()
    inventory = read(OUT / 'inventory.json')
    items = collect_rows()
    summary = {'protocol': PROTOCOL, 'status': read(OUT / 'run_metadata.json')['status'],
               'inventory': inventory, 'new_P7_runs': len(items), 'Joint': None, 'F': None, 'S': None,
               'measured': 0, 'technical_issues': [], 'credit': {}, 'D_gate_execution': False}
    if (OUT / 'manifest.json').exists():
        manifest = read(OUT / 'manifest.json')
        summary['qualification'] = {k: manifest[k] for k in ('qualified', 'excluded', 'preflight_passed', 'probe')}
        source, origins = load_memory(OUT / 'input_memory.jsonl'), read(OUT / 'origins.json')
        old_support = read(PARENT / 'observe/q_family_support.json')
        for policy in POLICIES:
            nodes, events, stats = credit_rows(items, source, origins, manifest, policy)
            support = {k: set(v) for k, v in old_support.items()}
            for event in events:
                if event['credited']:
                    support.setdefault(event['invariant_id'], set()).add(event['family_id'])
            stats['cards_with_two_feedback_families'] = sum(len(f) >= 2 for f in support.values())
            summary['credit'][policy] = stats
            if items:
                _write_memory(OUT / policy / 'frozen/m_star_q.jsonl', nodes)
                jsonl(OUT / policy / 'memory_q_events.jsonl', events)
                write(OUT / policy / 'q_family_support.json', {k: sorted(v) for k, v in support.items()})
        summary['technical_issues'] = [{'task_id': r['task_id'], 'issues': row_issues(r)} for r in items if row_issues(r)]
    if items:
        summary.update(measured=sum(bool(r.get('final', {}).get('measured')) for r in items),
                       Joint=sum(bool(r.get('final', {}).get('measured') and r['final'].get('joint')) for r in items),
                       F=sum(bool(r.get('final', {}).get('measured') and r['final'].get('functional')) for r in items),
                       S=sum(bool(r.get('final', {}).get('measured') and r['final'].get('security')) for r in items))
    initials = rows(OUT / 'shared_initial.jsonl')
    summary['cost'] = {'P7': {k: sum(r['accounting'][k] for r in items) for k in FIELDS},
                       'shared_initial': {k: sum(r['accounting'][k] for r in initials) for k in FIELDS},
                       'embedding': rows(OUT / 'embedding_segments.jsonl'), 'currency': None}
    jsonl(OUT / 'rows.jsonl', items)
    write(OUT / 'summary.json', summary)
    write(CURATED / 'summary.json', summary)
    return summary


def probe_gate(summary, expected):
    """工程门只判断可执行且有新跨族反馈；不是提分或显著性结论。"""
    checks = {'all12': summary['new_P7_runs'] == len(expected) == 12,
              'zero_technical_errors': not summary['technical_issues'],
              'complete_measurement': summary['measured'] == 12,
              'all_feedback_new_at_least6': summary['credit']['all_feedback']['new_cards'] >= 6,
              'cross_family_new_at_least3': summary['credit']['cross_family']['new_cards'] >= 3}
    return {'passed': all(checks.values()), 'checks': checks,
            'interpretation': 'coverage engineering gate only; not evidence of Q benefit'}


def run(stage):
    """显式付费：前2题技术门→12题覆盖门→最多1轮合格D_init；原生结果先落盘，无自动重跑。"""
    verify()
    manifest = read(OUT / 'manifest.json')
    if read(OUT / 'run_metadata.json')['status'].startswith('technical_stop'):
        raise RuntimeError('prior_technical_stop_requires_new_protocol')
    if not manifest['preflight_passed']:
        raise RuntimeError('preflight_gate_not_passed')
    existing = collect_rows()
    if any(row_issues(r) for r in existing):
        raise RuntimeError('prior_technical_stop_requires_new_protocol')
    if stage == 'learn' and not read(OUT / 'probe_gate.json')['passed']:
        raise RuntimeError('probe_gate_not_passed')
    identifiers = manifest['probe'] if stage == 'probe' else manifest['learning']
    done = {r['task_id'] for r in existing}
    missing = [i for i in identifiers if i not in done]
    if not missing:
        result = report()
        if stage == 'probe':
            write(OUT / 'probe_gate.json', probe_gate(result, manifest['probe']))
        return result
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    requester = _requester('deepseek-v3.2', 60, max_tokens=4096, max_inflight=1, thinking='disabled')
    embedding = EmbeddingClient(model='text-embedding-3-large', key_loader=load_key,
                                cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
    runner = frozen_runner()
    _, tasks, _ = inputs()
    bank = load_memory(OUT / 'input_memory.jsonl')
    before = [n.to_dict() for n in bank]
    shared = {i['task_id']: i for i in rows(OUT / 'shared_initial.jsonl')}
    meta = read(OUT / 'run_metadata.json')
    meta['status'] = 'running_' + stage
    write(OUT / 'run_metadata.json', meta)
    for identifier in missing:
        if identifier not in shared:
            req, tracker = account_request(requester, 'shared_initial')
            initial = prepare_shared_initial(tasks[identifier], req)
            initial['accounting'] = {k: tracker.snapshot()['total'][k] for k in FIELDS}
            shared[identifier] = initial
            jsonl(OUT / 'shared_initial.jsonl', shared.values())
        if shared[identifier].get('error_type'):
            meta['status'] = 'technical_stop_shared_initial'
            break
        req, tracker = account_request(requester, 'D_init_observer')
        started = perf_counter()
        native = None
        try:
            native = runner.run_one('PLT', tasks[identifier], 'P7', req, {'full': bank}, embedding,
                                    retrieval_mode='semantic_llm', delta=-1, lambda_q=.5,
                                    max_experiences=3, candidate_order=None,
                                    initial_analysis=copy.deepcopy(shared[identifier]['initial_analysis']))
            write(OUT / 'native_task_rows' / (identifier + '.json'), native)
            row = record_result(copy.deepcopy(native), tasks[identifier], 'Q0', 'D_init', perf_counter() - started)
        except Exception as exc:
            # 已发生过记录器丢结果；保留原生返回与用量，不重试/不打印可能含提示的异常正文。
            row = {**(native or {}), 'task_id': identifier, 'pool': 'D_init', 'family_id': tasks[identifier]['family_id'],
                   'worker_error': type(exc).__name__, 'attempts': (native or {}).get('attempts', [])}
        row.update(protocol=PROTOCOL, accounting={k: tracker.snapshot()['total'][k] for k in FIELDS})
        write(OUT / 'task_rows' / (identifier + '.json'), row)
        print({'stage': stage, 'task_id': identifier, 'issues': row_issues(row)}, flush=True)
        if row_issues(row):
            meta['status'] = 'technical_stop'
            break
        if stage == 'probe' and len(collect_rows()) == 2:
            write(OUT / 'smoke_gate.json', {'passed': True, 'tasks': manifest['probe'][:2],
                                          'meaning': 'technical P7 gate only'})
    else:
        meta['status'] = 'finished_' + stage
    if before != [n.to_dict() for n in bank]:
        raise RuntimeError('observer_generation_changed_bank')
    embedding_segments = rows(OUT / 'embedding_segments.jsonl')
    jsonl(OUT / 'embedding_segments.jsonl', embedding_segments + [{'stage': stage, **embedding.usage}])
    meta['new_P7_runs'] = len(collect_rows())
    write(OUT / 'run_metadata.json', meta)
    result = report()
    if stage == 'probe':
        write(OUT / 'probe_gate.json', probe_gate(result, manifest['probe']))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'preflight', 'probe', 'learn', 'report'])
    args = parser.parse_args()
    if args.stage == 'prepare':
        result = prepare()
    elif args.stage == 'preflight':
        result = preflight()
    elif args.stage == 'report':
        result = report()
    else:
        result = run(args.stage)
    print(json.dumps({k: v for k, v in result.items() if k not in {'all_tasks', 'learning', 'credit'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
