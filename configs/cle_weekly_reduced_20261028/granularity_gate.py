"""FG_GATE全298题三策略两重复；相同题/重复/档位只生成一次，策略逻辑格独立登记。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

from . import retest as base
from . import granularity as labels
from configs.cle_v41_completion_20261026.policies import features, predict, rule_level
from methods.cle_ablation.memory_granularity_study import run_one_level
from methods.sct_trajectory.memory_granularity import public_task, reviewed_binding
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

PROTOCOL = 'cle-weekly-full-granularity-policies-gate-20261027-v1'
MODEL_PROTOCOL = 'cle-reduced-granularity-family-router-20261028-v1'
POLICIES = ('fixed', 'rule', 'classifier')
SEED = 20261027


def package_root():
    return base.RUN/'FG_GATE'


def schedule(ids, tasks):
    rng, cells = random.Random(SEED), []
    for repeat in (1, 2):
        for tid in ids:
            policies = list(POLICIES)
            rng.shuffle(policies)
            cells.extend({'cell_id': f'{tid}_r{repeat}_{policy}', 'task_id': tid,
                'family_id': tasks[tid]['family_id'], 'repeat': repeat,
                'condition': policy, 'pool': 'D_gate'} for policy in policies)
    return cells


def prepare():
    inputs = package_root()/'inputs'
    if (inputs/'protocol.json').exists():
        return base.read(inputs/'protocol.json')
    source = base.RUN/'FQ_GATE/inputs_v3/tasks.json'
    material_inputs = base.RUN/'FG_LABELS/inputs'
    if not source.exists() or not (material_inputs/'protocol.json').exists():
        return {'status': 'awaiting_frozen_source_inputs', 'planned_P7': 1788}
    base.disk_check()
    tasks = base.read(source)
    ids = base.read(base.RUN/'manifest.json')['pools']['D_gate']
    if len(ids) != 298 or len(set(ids)) != 298 or set(ids) != set(tasks):
        raise ReplayStop('FG_GATE_requires_full_298_v3_tasks')
    zero = str(base.RUN/'shared_inputs/memory1939_q0.jsonl')
    protocol = {'protocol': PROTOCOL, 'package': 'FG_GATE', 'planned_P7': 1788,
        'task_count': 298, 'card_count': 1924, 'repeats': 2, 'conditions': list(POLICIES),
        'bank_sources': {policy: zero for policy in POLICIES}, 'paid_execution_enabled': False,
        'model_settings': base.wiring.SETTINGS, 'max_cards': 3, 'max_repairs': 1, 'workers_max': 4,
        'Q_updates': 0, 'Q_sorting': False, 'new_cards': 0,
        'model_source': str(base.RUN/'FG_TRAIN/model.json'), 'model_protocol': MODEL_PROTOCOL,
        'label_source_protocol': base.read(material_inputs/'protocol.json')['protocol'],
        'fixed_policy': 'best level selected only from FG_LABELS training outcomes',
        'rule_policy': 'original public rule_level(task, first_has_cards)',
        'classifier_policy': 'original predict(public task, newly frozen model); no target results or repair information',
        'routing_before_code_generation': True, 'routing_scope': 'public task features and shared first-selection presence only',
        'same_level_reuse_key': ['task_id', 'repeat', 'selected_level', 'first_start_identity'],
        'cross_repeat_generation_reuse': False,
        'first_initial_and_selection_shared_within': 'task x repeat only',
        'repair': 'native selected-level P7 code/feedback; L0 empty; distinct levels independent',
        'common_source_pool': 'same1924 eligible cards and same-family exclusion for all strategies',
        'levels_are_strictly_nested': False, 'source_task_file': str(source),
        'source_material_inputs': str(material_inputs), 'performance_gate_controls_dispatch': False,
        'budget_proposed': {'conservative_model_and_embedding_tokens': 1788*150000 + 3576*100000,
            'total_physical_HTTP_attempts': 1788*40 + 3576*2*4,
            'embedding_HTTP_attempts_included_in_total': 1788*16},
        'material_pair_upper_bound': 298*2*2*3,
        'budget_basis': 'at most3 unique levels per task-repeat; source-public bindings at most3cards x2attempts x2repeats per task, cached across strategies; native format/HTTP retries included',
        'formal_old_code_units_reused': 0, 'resume_budget_reset': False, 'unknown_HTTP_redispatch': False}
    write_json(inputs/'tasks.json', tasks)
    write_json(inputs/'schedule.json', schedule(ids, tasks))
    for name in ('source_examples.json', 'source_eligibility.json', 'family_split.json'):
        write_json(inputs/name, base.read(material_inputs/name))
    write_json(inputs/'protocol.json', protocol)
    write_json(inputs/'reuse_manifest.json', {'formal_old_code_units': 0,
        'dynamic_reuse': 'same current task-repeat-level with exact frozen start; final code and all attempts reused',
        'different_repeats': 'independent generation, never reuse code across repeats',
        'model_source': protocol['model_source'], 'old_classifier_allowed': False,
        'material_reuse': 'exact source/public legacy and completed FG_LABELS cached bindings only'})
    return protocol


def dependencies():
    reasons = []
    from .scope import CONTROL, read
    decision=read(CONTROL/'GR_decision.json') if (CONTROL/'GR_decision.json').exists() else {}
    if decision.get('action') != 'freeze_and_gate':
        reasons.append('adaptive_training_not_ready')
    package = base.RUN/'FG_LABELS'
    index = package/'execution_index.json'
    segments = base.read(index)['segments'] if index.exists() else []
    if not segments or not (Path(segments[-1])/'summary.json').exists():
        reasons.append('FG_LABELS_full_grid_not_completed')
    else:
        summary = base.read(Path(segments[-1])/'summary.json')
        if summary.get('status') != 'completed' or summary.get('completed') != 820:
            reasons.append('FG_LABELS_full_grid_not_completed')
    replay = package/'zero_API_replay/replay_result.json'
    if not replay.exists() or base.read(replay).get('status') != 'passed':
        reasons.append('FG_LABELS_native_replay_pending')
    analysis = package/'analysis/summary.json'
    if not analysis.exists() or base.read(analysis).get('status') != 'completed':
        reasons.append('FG_LABELS_analysis_pending')
    trained = base.RUN/'FG_TRAIN/summary.json'
    model = base.RUN/'FG_TRAIN/model.json'
    if not trained.exists() or base.read(trained).get('status') != 'completed' or not model.exists():
        reasons.append('new_FG_TRAIN_model_not_completed')
    else:
        value = base.read(model)
        source = package/'inputs/protocol.json'
        if value.get('protocol') != MODEL_PROTOCOL or not source.exists() or value.get('source_protocol') != base.read(source)['protocol']:
            reasons.append('classifier_does_not_match_current_full_labels')
    reference = base.RUN/'FQ_GATE/preflight_v3/summary.json'
    if not reference.exists() or any(base.read(reference).get(key) != expected for key, expected in
            [('reference_joint', 298), ('reference_and_name_checks_passed', 298), ('reference_preflight_ready', True)]):
        reasons.append('v3_full_gate_reference_preflight_pending')
    inputs = package_root()/'inputs'
    source = base.RUN/'FQ_GATE/inputs_v3/tasks.json'
    if not (inputs/'tasks.json').exists() or not source.exists() or base.read(inputs/'tasks.json') != base.read(source):
        reasons.append('FG_GATE_v3_task_snapshot_pending')
    check = package_root()/'offline_checks.json'
    if not check.exists() or base.read(check).get('status') != 'passed':
        reasons.append('FG_GATE_offline_checks_pending')
    return {'ready': not reasons, 'reasons': reasons, 'old_classifier_consumed': False,
        'real_dispatch_started_by_check': False}


def start_identity(start):
    return hashlib.sha256(json.dumps(start, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class FrozenPolicyGate(labels.FrozenGranularity):
    conditions = POLICIES
    controlled_conditions = POLICIES
    reference_bank = 'fixed'
    retrieval_bank = 'fixed'
    pool = 'D_gate'
    runner_module = 'configs.cle_weekly_reduced_20261028.granularity_gate'

    def package_directory(self):
        return package_root()

    def additional_protected_paths(self):
        return super().additional_protected_paths() + [Path(self.protocol['model_source'])]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = base.read(Path(self.protocol['model_source']))
        if (self.model.get('protocol') != MODEL_PROTOCOL or
                self.model.get('source_protocol') != self.protocol['label_source_protocol']):
            self.embedding._db.close()
            raise ReplayStop('only_new_full_FG_TRAIN_model_is_allowed')
        self.io.save('model_snapshot', self.model)
        self.route_cache, self.level_rows = {}, {}
        for row in self.rows if not self.offline else []:
            level = row.get('selected_level')
            if level not in labels.LEVELS or not row.get('first_start_identity'):
                self.embedding._db.close()
                raise ReplayStop('saved_policy_row_missing_frozen_route_identity')
            key = (row['task_id'], row['repeat'], level)
            previous = self.level_rows.get(key)
            if previous is not None and (previous['attempts'] != row['attempts'] or previous.get('usage') != row.get('usage')):
                self.embedding._db.close()
                raise ReplayStop('same_task_repeat_level_has_conflicting_completed_trajectories')
            self.level_rows[key] = row
        # 完成的学习标签材料可精确复用；它们不提供当前D_gate的成绩或策略标签。
        prior_materials = base.RUN/'FG_LABELS/shared_materials/bindings'
        for path in prior_materials.glob('*.json'):
            binding = base.read(path)
            source, public = binding.get('source_projection'), binding.get('public_task')
            if source is None or public is None:
                raise ReplayStop('completed_FG_LABELS_binding_missing_full_identity')
            identity = labels.binding_hash(source, public)
            if identity != binding.get('source_public_sha256') or identity[:20] != path.stem:
                raise ReplayStop('completed_FG_LABELS_binding_identity_changed')
            reviewed_binding(source, public, binding)
            self.materials.legacy[identity] = {'source': source, 'public': public, 'binding': binding, 'path': str(path)}

    def route(self, cell, start):
        key = (cell['task_id'], cell['repeat'])
        identity = start_identity(start)
        with self.lock:
            if key in self.route_cache:
                decision = self.route_cache[key]
                if decision['first_start_identity'] != identity:
                    raise ReplayStop('policy_route_shared_start_changed')
                return decision
            task = self.tasks[cell['task_id']]
            has_cards = bool(start['selected_cards'])
            predicted, confidence = predict(task, self.model)
            levels = {'fixed': self.model['fixed'], 'rule': rule_level(task, has_cards), 'classifier': predicted}
            if any(level not in labels.LEVELS for level in levels.values()):
                raise ReplayStop('router_returned_unknown_memory_level')
            decision = {'task_id': cell['task_id'], 'repeat': cell['repeat'],
                'first_start_identity': identity, 'first_has_cards': has_cards,
                'selected_levels': levels, 'classifier_confidence': confidence,
                'public_features': features(task), 'public_task': public_task(task),
                'routing_before_any_code_for_this_task_repeat': True,
                'repair_or_outcomes_used_for_routing': False, 'model_protocol': self.model['protocol']}
            for source in self.sources:
                path = source/'routing'/f'{cell["task_id"]}_r{cell["repeat"]}.json'
                if path.exists() and base.read(path) != decision:
                    raise ReplayStop('saved_policy_route_differed_from_frozen_model_and_start')
            self.io.save(f'routing/{cell["task_id"]}_r{cell["repeat"]}', decision)
            self.route_cache[key] = decision
            return decision

    def one(self, cell, start):
        decision = self.route(cell, start)
        level = decision['selected_levels'][cell['condition']]
        key = (cell['task_id'], cell['repeat'], level)
        with self.lock:
            source = self.level_rows.get(key)
        if source is not None:
            if source['first_start_identity'] != decision['first_start_identity']:
                raise ReplayStop('same_level_reuse_start_mismatch')
            row = copy.deepcopy(source)
            row.update(cell, arm=cell['condition'], memory_policy=cell['condition'], selected_level=level,
                memory_level=level, result_reused=True, reused_from_cell=source['cell_id'],
                canonical_generation_cell=source.get('canonical_generation_cell', source['cell_id']))
            self.io.save('task_rows/'+cell['cell_id'], row)
            with self.lock:
                self.rows.append(row)
                self.checkpoint('running_replay' if self.offline else 'running')
            return row
        row = super().one(cell, start)
        with self.lock:
            self.level_rows[key] = copy.deepcopy(row)
        return row

    def run_p7(self, cell, start, request):
        decision = self.route(cell, start)
        level = decision['selected_levels'][cell['condition']]
        row = run_one_level(self.tasks[cell['task_id']], start, level, request,
            lambda query: self.retrieve(query, request), self.materials.level_materials)
        row.update(selected_level=level, memory_policy=cell['condition'],
            first_start_identity=decision['first_start_identity'], first_has_cards=decision['first_has_cards'],
            routing_before_generation=True, result_reused=False,
            canonical_generation_cell=cell['cell_id'])
        return row

    def decorate_row(self, row, cell):
        if row.get('preparation_blocked_reason'):
            raise ReplayStop('granularity_material_preparation_blocked:'+row['preparation_blocked_reason'])
        row.update(arm=cell['condition'], memory_policy=cell['condition'],
            memory_level=row['selected_level'], Q_sorting=False, levels_are_strictly_nested=False,
            code_implementation_verified=None)

    def inspect_native_row(self, row):
        if row.get('selected_level') != 'L0':
            return base.FrozenRetest.inspect_native_row(self, row)
        assert 1 <= len(row['attempts']) <= 2 and row['final'] == row['attempts'][-1]
        assert not (len(row['attempts']) == 2 and row['attempts'][0].get('joint'))
        assert all(not a.get('generation', {}).get('retrieved_cards') and
                   not a.get('generation', {}).get('cards') for a in row['attempts'])

    @staticmethod
    def selection_check(rows):
        selections, empty_violation = {}, False
        for row in rows:
            trace = row['attempts'][0].get('retrieval_trace') or {}
            if trace.get('status') == 'completed' and 'pre_level_selected_ids' in trace:
                selections[row['condition']] = trace['pre_level_selected_ids']
            if row.get('selected_level') == 'L0':
                empty_violation |= any(a.get('generation', {}).get('retrieved_cards') or
                    a.get('generation', {}).get('cards') for a in row['attempts'])
        values = list(selections.values())
        mismatch = any(v != values[0] for v in values[1:]) if values else False
        return {'status': 'different' if mismatch or empty_violation else 'passed' if len(selections) == 3 else 'incomplete_model_or_retrieval_measurement',
            'matched_policies': sorted(selections), 'pre_level_selected_ids': values[0] if values else None,
            'L0_memory_violation': bool(empty_violation), 'Q_updates': 0}

    def checkpoint(self, status):
        summary = super().checkpoint(status)
        canonical = {row.get('canonical_generation_cell', row['cell_id']) for row in self.rows}
        summary.update(logical_completed=len(self.rows), completed_unique_level_runs=len(canonical),
            reused_logical_cells=sum(bool(row.get('result_reused')) for row in self.rows),
            independent_repeat_key='task_id x repeat x selected_level',
            actual_paid_level_runs=0 if self.offline else len(canonical))
        self.io.save('summary', summary)
        self.io.state.update(completed_unique_level_runs=len(canonical),
            actual_paid_P7=0 if self.offline else len(canonical), completed_P7=len(self.rows))
        self.io.save('state', self.io.state)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'launch', 'run', 'resume', 'replay'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    FrozenPolicyGate.worker_limit = args.workers
    if args.action == 'prepare':
        value = prepare()
        print(json.dumps({'status': value.get('status', 'prepared_zero_API'), 'planned': value['planned_P7'], 'dependencies': dependencies()}))
        return
    dep = dependencies()
    if args.action == 'check':
        print(json.dumps(dep))
        return
    if args.action != 'replay' and not dep['ready']:
        raise ReplayStop('FG_GATE_not_ready:'+','.join(dep['reasons']))
    index = package_root()/'execution_index.json'
    sources = [Path(path) for path in base.read(index)['segments']] if index.exists() else []
    if args.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(base.wiring.SETTINGS['model'])
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_reduced_20261028.granularity_gate run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
        if actual.stdout.strip():
            print(json.dumps({'status': 'already_running'}))
            return
        with (package_root()/'stdout.log').open('a', encoding='utf-8') as stdout, (package_root()/'stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_reduced_20261028.granularity_gate', 'run', '--workers', str(args.workers)], cwd=base.ROOT,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(package_root()/'launch.json', {'pid': process.pid, 'started_utc': base.now()})
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
        return
    if args.action == 'replay':
        if not sources or base.read(sources[-1]/'summary.json').get('completed') != 1788:
            raise ReplayStop('full_1788_completed_cells_required_for_FG_GATE_replay')
        target = package_root()/'zero_API_replay'
        if (target/'replay_result.json').exists():
            print(json.dumps(base.read(target/'replay_result.json')))
            return
        FrozenPolicyGate(sources, offline=True, destination=target).execute()
        return
    import msvcrt
    with (package_root()/'execution.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if sources and args.action != 'resume':
                raise ReplayStop('existing_segments_require_explicit_reconciliation_or_replay')
            target = package_root()/f'segment_{len(sources)+1:03d}'
            study = FrozenPolicyGate(sources, destination=target)
            write_json(index, {'segments': list(map(str, sources))+[str(target)]})
            study.execute()
            write_json(package_root()/'completion.json', {'status': 'awaiting_agent_analysis', 'planned': 1788,
                'updated_utc': base.now()})
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
