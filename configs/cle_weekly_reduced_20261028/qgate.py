"""FQ_GATE全298题四臂两重复；复用冻结回测请求、恢复、原P7与验证层。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys

from . import retest
from methods.cle_ablation.run_memory_q import shuffled_memory
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

PROTOCOL = 'cle-weekly-frozen-gate-four-conditions-20261027-v1'
CONDITIONS = ('Q0', 'Q1', 'Q2', 'Q3')
CONTROLLED_CONDITIONS = ('Q1', 'Q2', 'Q3')
SEED = 20261027
PERMUTATION_SEED = 20261015


def package_root():
    return retest.RUN / 'FQ_GATE'


def schedule(ids, tasks):
    """固定全298题和两重复，每组四条件随机顺序，成绩不进入排程。"""
    rng = random.Random(SEED)
    cells = []
    for repeat in (1, 2):
        for tid in ids:
            arms = list(CONDITIONS)
            rng.shuffle(arms)
            cells.extend({'cell_id': f'{tid}_r{repeat}_{arm}', 'task_id': tid,
                'family_id': tasks[tid]['family_id'], 'repeat': repeat, 'condition': arm,
                'pool': 'D_gate'} for arm in arms)
    return cells


def prepare():
    """只冻结本包规格，公开修订题已由原始来源核对流程提供；不改学习输入。"""
    inputs = package_root() / 'inputs_v3'
    if (inputs / 'protocol.json').exists():
        return retest.read(inputs / 'protocol.json')
    retest.disk_check()
    tasks = retest.read(inputs / 'tasks.json')
    ids = retest.read(retest.RUN / 'manifest.json')['pools']['D_gate']
    if len(ids) != 298 or len(set(ids)) != 298 or set(ids) != set(tasks):
        raise ReplayStop('gate_requires_original_full_298_manifest')
    for tid in ids:
        if str(tasks[tid]['index']) != tid:
            raise ReplayStop('gate_task_identity_mismatch:' + tid)
    cells = schedule(ids, tasks)
    zero = str(retest.RUN / 'shared_inputs/memory1939_q0.jsonl')
    final = str(retest.RUN / 'FQ_LEARN/frozen/K3.jsonl')
    protocol = {'protocol': PROTOCOL, 'package': 'FQ_GATE', 'planned_P7': 2384,
        'task_count': 298, 'card_count': 1939, 'repeats': 2, 'conditions': list(CONDITIONS),
        'bank_sources': {'Q0': zero, 'Q1': zero, 'Q2': final, 'Q3': final},
        'bank_transforms': {'Q3': {'kind': 'shuffle_Q_and_visits_within_CWE', 'seed': PERMUTATION_SEED}},
        'model_settings': retest.wiring.SETTINGS, 'retrieval_mode': 'semantic_llm',
        'max_cards': 3, 'max_repairs': 1, 'workers_max': 4, 'Q_updates': 0, 'new_cards': 0,
        'Q0_definition': 'original vector-plus-lexical candidate order, no similarity threshold, original LLM terminal selection',
        'Q1_definition': 'cosine order, strict cosine > -1, same LLM terminal selection',
        'Q2_definition': 'cosine plus frozen K3 Q order, strict cosine > -1, same LLM terminal selection',
        'Q3_definition': 'Q2 with within-CWE deterministic paired (Q,visits) permutation',
        'Q0_candidate_order': None, 'Q0_delta': None,
        'controlled_candidate_delta': -1, 'lambda_q': .5,
        'controlled_conditions': list(CONTROLLED_CONDITIONS), 'primary_comparisons': ['Q2-Q1', 'Q2-Q3'],
        'Q0_boundary_interpretation': 'original system reference; unthresholded candidate boundary may differ, not pure Q attribution',
        'additional_control_arm': False, 'first_initial_shared_within': 'task x repeat only; repeats independent',
        'first_candidates': 'Q1/Q2/Q3 same query, recall, cosine and threshold; actual traces checked',
        'repair_queries': 'independent per condition code and original permitted feedback',
        'public_contract_file': str(inputs / 'tasks.json'),
        'reference_preflight': str(package_root() / 'preflight_v3/summary.json'),
        'source_learning_protocol': retest.read(retest.RUN / 'protocol.json')['protocol'],
        'completed_learning_required': ['K0', 'K1', 'K2', 'K3'],
        'completed_retest_required': 1416, 'paid_execution_enabled': False,
        'performance_gate_controls_dispatch': False,
        'budget_proposed': {'conservative_model_and_embedding_tokens': 2384 * 150000,
            'total_physical_HTTP_attempts': 2384 * 40,
            'embedding_HTTP_attempts_included_in_total': 2384 * 16},
        'budget_basis': 'same bounded per-P7 engineering cap as fixed learning and retest; all shared calls and native retries included',
        'formal_historical_code_reuse': 0, 'resume_budget_reset': False,
        'unknown_HTTP_redispatch': False}
    write_json(inputs / 'schedule.json', cells)
    write_json(inputs / 'protocol.json', protocol)
    write_json(inputs / 'reuse_manifest.json', {'formal_old_code_units': 0,
        'reason': 'new K3 and unified public contract version require current frozen four-condition outputs',
        'allowed': ['exact text/model embeddings', 'same task-repeat first initial', 'completed exact cells and responses during recovery'],
        'not_allowed': ['learning or retest code substituted for gate', 'one generation credited to two repeats', 'different public contract version']})
    return protocol


def dependencies():
    """学习、同题回测及真实参考预检都完成后才能派发；没有收益门。"""
    reasons = list(retest.dependencies()['reasons'])
    reference = package_root() / 'preflight_v3/summary.json'
    if not reference.exists():
        reasons.append('gate_reference_preflight_missing')
    else:
        evidence = retest.read(reference)
        if (evidence.get('reference_joint') != 298 or evidence.get('reference_and_name_checks_passed') != 298
                or evidence.get('reference_preflight_ready') is not True):
            reasons.append('gate_reference_298_preflight_not_ready')
    previous = retest.RUN / 'FQ_RETEST'
    index = previous / 'execution_index.json'
    segments = retest.read(index)['segments'] if index.exists() else []
    if not segments or not (Path(segments[-1]) / 'summary.json').exists():
        reasons.append('FQ_RETEST_not_completed')
    else:
        summary = retest.read(Path(segments[-1]) / 'summary.json')
        if summary.get('status') != 'completed' or summary.get('completed') != 1416:
            reasons.append('FQ_RETEST_not_completed')
    replay = previous / 'zero_API_replay/replay_result.json'
    if not replay.exists() or retest.read(replay).get('status') != 'passed':
        reasons.append('FQ_RETEST_native_replay_pending')
    analysis = previous / 'analysis/summary.json'
    if not analysis.exists() or retest.read(analysis).get('status') != 'completed':
        reasons.append('FQ_RETEST_analysis_pending')
    return {'ready': not reasons, 'reasons': reasons}


class FrozenGate(retest.FrozenRetest):
    """Q0边界只做诊断；Q1/Q2/Q3复用完全相同的受控候选核对与原生流程。"""

    conditions = CONDITIONS
    controlled_conditions = CONTROLLED_CONDITIONS
    pool = 'D_gate'
    runner_module = 'configs.cle_weekly_reduced_20261028.qgate'

    def package_directory(self):
        return package_root()

    def input_directory(self):
        return self.package_directory() / 'inputs_v3'

    def load_banks(self):
        banks = super().load_banks()
        banks['Q3'] = shuffled_memory(banks['Q3'], PERMUTATION_SEED, scope='cwe')
        return banks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.io.save('Q3_permutation', {'scope': 'cwe', 'seed': PERMUTATION_SEED,
            'source': self.protocol['bank_sources']['Q3'],
            'states': [{'invariant_id': card.invariant_id, 'cwe': str(card.cwe),
                        'q_value': card.q_value, 'q_visits': card.q_visits} for card in self.banks['Q3']]})

    def policy(self, arm):
        return {'candidate_order': None if arm == 'Q0' else 'similarity' if arm == 'Q1' else 'q',
                'delta': None if arm == 'Q0' else -1, 'record_arm': arm,
                'Q_checkpoint': 'K3' if arm in ('Q2', 'Q3') else None}

    def after_group(self, rows, check):
        by = {row['condition']: row for row in rows}
        q0, q1 = by['Q0']['attempts'][0], by['Q1']['attempts'][0]
        ta, tb = q0.get('retrieval_trace') or {}, q1.get('retrieval_trace') or {}
        measured = ta.get('status') == tb.get('status') == 'completed'
        a = ta.get('presented_candidate_ids', ta.get('candidate_ids', []))
        b = tb.get('presented_candidate_ids', tb.get('candidate_ids', []))
        self.io.save(f'Q0_boundary/{rows[0]["task_id"]}_r{rows[0]["repeat"]}', {
            'task_id': rows[0]['task_id'], 'repeat': rows[0]['repeat'],
            'status': 'measured' if measured else 'unmeasured',
            'Q0_original_unthresholded': True, 'Q1_strict_cosine_gt': -1,
            'Q0_presented_count': len(a) if measured else None,
            'Q1_presented_count': len(b) if measured else None,
            'same_presented_members': set(a) == set(b) if measured else None,
            'Q0_only_presented_ids': sorted(set(a)-set(b)) if measured else None,
            'primary_controlled_check': check['status'],
            'interpretation': 'Q0 reference boundary differences are not isolated Q effects; no fifth paid arm'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'launch', 'run', 'resume', 'replay'])
    args = parser.parse_args()
    if args.action == 'prepare':
        protocol = prepare()
        print(json.dumps({'status': 'prepared_zero_API', 'planned': protocol['planned_P7'], 'dependencies': dependencies()}))
        return
    gate = package_root() / 'offline_checks.json'
    dep = dependencies()
    if args.action == 'check':
        print(json.dumps({'dependencies': dep, 'offline_checks': retest.read(gate) if gate.exists() else None}))
        return
    if args.action != 'replay' and (not dep['ready'] or not gate.exists() or retest.read(gate).get('status') != 'passed'):
        raise ReplayStop('frozen_gate_not_ready:' + ','.join(dep['reasons']))
    index_path = package_root() / 'execution_index.json'
    sources = [Path(p) for p in retest.read(index_path)['segments']] if index_path.exists() else []
    if args.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(retest.wiring.SETTINGS['model'])
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_reduced_20261028.qgate run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
        if actual.stdout.strip():
            print(json.dumps({'status': 'already_running'}))
            return
        with (package_root() / 'stdout.log').open('a', encoding='utf-8') as stdout, (package_root() / 'stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_reduced_20261028.qgate', 'run'], cwd=retest.ROOT,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(package_root() / 'launch.json', {'pid': process.pid, 'started_utc': retest.now()})
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
        return
    if args.action == 'replay':
        if not sources or retest.read(sources[-1] / 'summary.json').get('completed') != 2384:
            raise ReplayStop('full_2384_completed_cells_required_for_gate_replay')
        destination = package_root() / 'zero_API_replay'
        if (destination / 'replay_result.json').exists():
            print(json.dumps(retest.read(destination / 'replay_result.json')))
            return
        FrozenGate(sources, offline=True, destination=destination).execute()
        return
    import msvcrt
    with (package_root() / 'execution.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if sources and args.action != 'resume':
                raise ReplayStop('existing_segments_require_explicit_reconciliation_or_replay')
            destination = package_root() / f'segment_{len(sources)+1:03d}'
            study = FrozenGate(sources, destination=destination)
            write_json(index_path, {'segments': list(map(str, sources)) + [str(destination)]})
            study.execute()
            write_json(package_root() / 'completion.json', {'status': 'awaiting_agent_analysis',
                'planned': 2384, 'updated_utc': retest.now()})
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
