"""FG_LABELS全D_grow五档两重复：原生粒度消费者，Q关闭，冻结来源与公开绑定。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import threading

from . import retest as base
from configs.cle_v41_completion_20261026.materials import Materials
from methods.cle_ablation.memory_granularity_study import run_one_level
from methods.sct_trajectory.memory_granularity import public_task, reviewed_binding
from methods.sct_trajectory.memory_views import source_projection
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

PROTOCOL = 'cle-weekly-full-granularity-labels-20261027-v1'
LEVELS = ('L0', 'L1', 'L2', 'L3', 'L4')
MEMORY_LEVELS = LEVELS[1:]
SEED = 20261027
RAW = base.ROOT/'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'
OLD = base.ROOT/'translation_work/diagnostics/20261026/cle_v41_completion'


def package_root():
    return base.RUN/'FG_LABELS'


def task_source():
    return package_root()/'inputs_contract_v2/tasks.json'


def reference_source():
    return package_root()/'preflight_contract_v2/summary.json'


def binding_hash(source, public):
    return hashlib.sha256(json.dumps([source, public], sort_keys=True).encode()).hexdigest()


def schedule(ids, tasks):
    rng, cells = random.Random(SEED), []
    for repeat in (1, 2):
        for tid in ids:
            levels = list(LEVELS)
            rng.shuffle(levels)
            cells.extend({'cell_id': f'{tid}_r{repeat}_{level}', 'task_id': tid,
                'family_id': tasks[tid]['family_id'], 'repeat': repeat,
                'condition': level, 'pool': 'D_grow'} for level in levels)
    return cells


def old_binding_catalog():
    """按完整旧source与旧public重建原缓存身份，并验证双方逐字引用。"""
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.ablation import get_config
    engine = HskTreeRetriever(HskTree(), requester=lambda _: (_ for _ in ()).throw(ReplayStop('old_binding_catalog_no_API')),
        ablation=get_config('A7'), retrieval_mode='semantic_llm')
    nodes = {node.invariant_id: node for node in base.runner.load_memory(OLD/'shared_inputs/memory1939.jsonl')}
    catalog = {}
    for path in (OLD/'shared_materials/bindings').glob('*.json'):
        binding = base.read(path)
        card = engine._to_card({'language': 'python'}, nodes[binding['card_id']], base=0., llm=None)
        source, public = source_projection(card), binding['public_task']
        identity = binding_hash(source, public)
        if identity[:20] != path.stem:
            raise ReplayStop('old_binding_source_identity_changed:' + path.stem)
        reviewed_binding(card, public, binding)
        catalog[identity] = {'source': source, 'public': public, 'binding': binding, 'path': str(path)}
    return catalog


class LockedGranularityMaterials(Materials):
    """L1/L2规则不请求模型；L3缺失绑定串行生成；L4只消费冻结历史来源。"""

    def __init__(self, root, io, examples, sources=()):
        super().__init__(root, io.request_for)
        self.io, self.examples = io, examples
        self.sources = [Path(path) for path in sources]
        self.lock = threading.RLock()
        self.legacy = old_binding_catalog()

    def level_materials(self, cards, task, level):
        with self.lock:
            public = public_task(task)
            for card in cards if level == 'L3' else []:
                source = source_projection(card)
                identity = binding_hash(source, public)
                path = self.root/'bindings'/(identity[:20]+'.json')
                if path.exists():
                    binding = base.read(path)
                    if (binding.get('source_public_sha256') != identity
                            or binding.get('source_projection') != source or binding.get('public_task') != public):
                        raise ReplayStop('local_binding_requires_exact_source_public_reconciliation')
                else:
                    saved_paths = [root/'used_bindings'/(identity+'.json') for root in reversed(self.sources)]
                    saved = next((p for p in saved_paths if p.exists()), None)
                    evidence = base.read(saved) if saved else self.legacy.get(identity)
                    if evidence is not None:
                        if evidence['source'] != source or evidence['public'] != public:
                            raise ReplayStop('saved_binding_source_public_mismatch')
                        binding = copy.deepcopy(evidence['binding'])
                        reviewed_binding(card, task, binding)
                        binding.update(source_public_sha256=identity, source_projection=source)
                        write_json(path, binding)
            # 原Materials保留最多两次格式尝试及原字段fallback，完整调用经本包io。
            result = super().level_materials(cards, task, level)
            for card in cards if level == 'L3' else []:
                source = source_projection(card)
                identity = binding_hash(source, public)
                binding = result['bindings'][card['invariant_id']]
                reviewed_binding(card, task, binding)
                binding.update(source_public_sha256=identity, source_projection=source,
                    not_human_gold=True)
                path = self.root/'bindings'/(identity[:20]+'.json')
                write_json(path, binding)
                self.io.save('used_bindings/'+identity, {'source_public_sha256': identity,
                    'source': source, 'public': public, 'binding': binding,
                    'annotation_method': binding.get('annotation_method') or 'AI_public_source_mapping_not_human_gold',
                    'original_reviewer': binding.get('reviewer'), 'not_human_gold': True})
            return result


def split_families(tasks):
    """保留既有36/12题族角色，其余题族在新成绩产生前按固定种子分配。"""
    all_families = {str(task['family_id']) for task in tasks.values()}
    prior = {name: {str(t['family_id']) for t in base.read(RAW/'v2'/f'tasks_{name}.json')}
             for name in ('train', 'development')}
    if prior['train'] & prior['development']:
        raise ReplayStop('legacy_training_development_families_overlap')
    if not (prior['train'] | prior['development']) <= all_families:
        raise ReplayStop('legacy_training_development_families_outside_current_Dgrow')
    remaining = sorted(all_families-prior['train']-prior['development'])
    random.Random(SEED).shuffle(remaining)
    cut = math.ceil(len(remaining)*.75)
    train, dev = prior['train'] | set(remaining[:cut]), prior['development'] | set(remaining[cut:])
    fold_families = sorted(train)
    random.Random(SEED).shuffle(fold_families)
    return {'seed': SEED, 'prior_train_families': sorted(prior['train']),
        'prior_development_families': sorted(prior['development']),
        'train_families': sorted(train), 'development_families': sorted(dev),
        'by_task': {tid: 'train' if str(task['family_id']) in train else 'development' for tid, task in tasks.items()},
        'train_task_ids': [tid for tid, task in tasks.items() if str(task['family_id']) in train],
        'development_task_ids': [tid for tid, task in tasks.items() if str(task['family_id']) in dev],
        'task_family': {tid: str(task['family_id']) for tid, task in tasks.items()},
        'family_cv_fold': {family: index % 3 for index, family in enumerate(fold_families)},
        'cv_folds': 3, 'CV_scope': 'training families only; all rows/repeats of a family share its fold',
        'new_outcomes_used_to_split': False, 'classifier_trained': False}


def legacy_full_prepare_not_used():
    inputs = package_root()/'inputs'
    if (inputs/'protocol.json').exists():
        return base.read(inputs/'protocol.json')
    if not task_source().exists() or not reference_source().exists():
        return {'status': 'awaiting_repaired_D_grow_inputs', 'planned_P7': 2730,
            'task_source': str(task_source()), 'preflight_source': str(reference_source())}
    reference = base.read(reference_source())
    if (reference.get('reference_preflight_ready') is not True or reference.get('reference_joint') != 273
            or reference.get('reference_and_name_checks_passed') != 273):
        return {'status': 'awaiting_repaired_D_grow_preflight', 'planned_P7': 2730}
    base.disk_check()
    tasks = base.read(task_source())
    ids = base.read(base.RUN/'manifest.json')['pools']['D_grow']
    if len(ids) != 273 or len(set(ids)) != 273 or set(ids) != set(tasks):
        raise ReplayStop('FG_requires_original_full_273_manifest')
    from configs.cle_memory_mechanisms_20261023.prepare_granularity_views import load_materials
    examples = load_materials()[2]
    excluded = base.read(RAW/'C01_source_availability_v1/summary.json')['L4_unavailable_cards']
    bank_path = base.RUN/'shared_inputs/memory1939_q0.jsonl'
    nodes = base.runner.load_memory(bank_path)
    eligible = [n for n in nodes if n.invariant_id not in set(excluded)]
    if len(excluded) != 15 or len(eligible) != 1924 or any(n.invariant_id not in examples for n in eligible):
        raise ReplayStop('FG_common_source_eligibility_not_1924')
    frozen_examples = {n.invariant_id: examples[n.invariant_id] for n in eligible}
    cells = schedule(ids, tasks)
    families = split_families(tasks)
    protocol = {'protocol': PROTOCOL, 'package': 'FG_LABELS', 'planned_P7': 2730,
        'task_count': 273, 'card_count': 1924, 'original_card_count': 1939, 'conditions': list(LEVELS),
        'repeats': 2, 'bank_sources': {level: str(bank_path) for level in LEVELS},
        'paid_execution_enabled': False, 'model_settings': base.wiring.SETTINGS,
        'max_cards': 3, 'max_repairs': 1, 'workers_max': 4, 'Q_updates': 0, 'Q_sorting': False,
        'new_cards': 0, 'excluded_source_cards': excluded, 'source_family_exclusion_applies_to_all_levels': True,
        'first_initial_and_selection_shared_within': 'task x repeat only; repeats independent',
        'retrieval': 'original CLE vector+lexical order and LLM selector; Q disabled, identical1924 common source pool with same-family exclusions',
        'repair': 'per-level code and original permitted feedback; L0 empty in repair',
        'levels_are_strictly_nested': False, 'L3': 'L2 core principles plus target operation binding',
        'L4': 'L2 core principles plus historical source example, without L3 binding template',
        'source_examples_file': str(inputs/'source_examples.json'),
        'source_eligibility_file': str(inputs/'source_eligibility.json'),
        'family_split_file': str(inputs/'family_split.json'),
        'source_task_file': str(task_source()), 'reference_preflight': str(reference_source()),
        'L3_materials': 'exact source+public bindings reused; only selected uncached pairs generated through original Materials',
        'binding_format_attempts_max': 2, 'material_methods': 'AI or original source/public rule fallback; not human semantic gold',
        'performance_gate_controls_dispatch': False, 'formal_old_code_units_reused': 0,
        'budget_proposed': {'conservative_model_and_embedding_tokens': 2730*150000 + 3276*100000,
            'total_physical_HTTP_attempts': 2730*40 + 3276*2*4,
            'embedding_HTTP_attempts_included_in_total': 2730*16},
        'material_pair_upper_bound': 273*2*2*3,
        'material_budget_basis': 'L3:273 tasks x2 repeats x2 code attempts x at most3 selected cards, two format calls and native physical retries; cache reuse reduces actual use',
        'resume_budget_reset': False, 'unknown_HTTP_redispatch': False,
        'classifier_training': 'separate later offline step; no classifier dispatch here'}
    write_json(inputs/'tasks.json', tasks)
    write_json(inputs/'schedule.json', cells)
    write_json(inputs/'source_examples.json', frozen_examples)
    write_json(inputs/'source_eligibility.json', {'excluded_ids': excluded,
        'eligible_ids': [n.invariant_id for n in eligible], 'common_pool_count': 1924,
        'source_family_by_card': {key: str(value['source_family_id']) for key, value in frozen_examples.items()}})
    write_json(inputs/'family_split.json', families)
    write_json(inputs/'protocol.json', protocol)
    write_json(inputs/'reuse_manifest.json', {'formal_old_code_units': 0,
        'source_examples': 'exact historical examples frozen, unavailable15 excluded in all levels',
        'old_bindings': 'revalidate complete source+current public; prior241 estimate is not a current reuse count',
        'generation_reuse': 'only exact completed cell/saved response; never share outputs between repeats'})
    return protocol


def prepare():
    return base.read(package_root()/'inputs/protocol.json')


def dependencies():
    reasons = []
    if not reference_source().exists():
        reasons.append('repaired_Dgrow_reference_preflight_missing')
    else:
        value = base.read(reference_source())
        if (value.get('reference_preflight_ready') is not True or value.get('reference_joint') != 273
                or value.get('reference_and_name_checks_passed') != 273):
            reasons.append('repaired_Dgrow_reference_preflight_not_ready')
    copied = package_root()/'inputs/tasks.json'
    if not copied.exists() or not task_source().exists() or base.read(copied) != {i:base.read(task_source())[i] for i in base.read(copied)}:
        reasons.append('FG_repaired_task_snapshot_not_ready')
    check = package_root()/'offline_checks.json'
    if not check.exists() or base.read(check).get('status') != 'passed':
        reasons.append('FG_offline_checks_pending')
    return {'ready': not reasons, 'reasons': reasons, 'learning_or_K3_dependency': False,
        'classifier_trained': False, 'real_dispatch_started_by_check': False}


class FrozenGranularity(base.FrozenRetest):
    conditions = LEVELS
    controlled_conditions = MEMORY_LEVELS
    reference_bank = 'L2'
    retrieval_bank = 'L2'
    pool = 'D_grow'
    runner_module = 'configs.cle_weekly_reduced_20261028.granularity'

    def package_directory(self):
        return package_root()

    def load_banks(self):
        inputs = self.input_directory()
        self.examples = base.read(inputs/'source_examples.json')
        self.eligibility = base.read(inputs/'source_eligibility.json')
        excluded = set(self.eligibility['excluded_ids'])
        banks = {level: [node for node in nodes if node.invariant_id not in excluded]
                 for level, nodes in super().load_banks().items()}
        if any(node.invariant_id not in self.examples for nodes in banks.values() for node in nodes):
            raise ReplayStop('eligible_card_missing_frozen_source_example')
        return banks

    def additional_protected_paths(self):
        return [self.input_directory()/name for name in ('source_examples.json', 'source_eligibility.json', 'family_split.json')]

    def policy(self, arm):
        return {'candidate_order': None, 'delta': None, 'record_arm': 'Q0', 'Q_checkpoint': None}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if any(node.q_value != 0 or node.q_visits != 0 for nodes in self.banks.values() for node in nodes):
            self.embedding._db.close()
            raise ReplayStop('FG_requires_zero_Q_bank')
        root = self.out/'replay_material_cache' if self.offline else self.package_directory()/'shared_materials'
        self.materials = LockedGranularityMaterials(root, self.io, self.examples, self.sources)

    def retrieve(self, query, request):
        from methods.sct_trajectory.retriever import HskTreeRetriever
        from methods.sct_trajectory.hsk_tree import HskTree
        from methods.sct_trajectory.ablation import get_config
        family = str(self.tasks[str(query['task_id'])]['family_id'])
        nodes = [n for n in self.banks[self.retrieval_bank] if str(self.examples[n.invariant_id]['source_family_id']) != family]
        engine = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=self.embedding, semantic_delta=None, candidate_order=None)
        cards = engine.search(query, limit=3, pool_nodes=nodes)
        return cards, engine.last_hier_trace

    def start(self, task, repeat):
        key = f'{task["index"]}_r{repeat}'
        for previous in reversed(self.sources):
            path = previous/'shared_starts'/(key+'.json')
            if path.exists():
                saved = base.read(path)
                if all(k in saved for k in ('query', 'selected_cards', 'retrieval_trace')):
                    self.io.save('shared_starts/'+key, saved)
                    return saved
        saved = super().start(task, repeat)
        public = base.runner.plt_contract(task)
        query = {**public, 'threat_analysis': saved['initial_analysis'], 'current_code': '', 'failure_evidence': {}}
        cards, trace = self.retrieve(query, self.io.request_for('shared_selection_'+key))
        if self.io.reason:
            raise ReplayStop(self.io.reason)
        saved.update(public_contract=public, query=query, selected_cards=cards, retrieval_trace=trace, repeat=repeat)
        self.io.save('shared_starts/'+key, saved)
        return saved

    def run_p7(self, cell, start, request):
        return run_one_level(self.tasks[cell['task_id']], start, cell['condition'], request,
            lambda query: self.retrieve(query, request), self.materials.level_materials)

    def inspect_native_row(self, row):
        if row['condition'] != 'L0':
            return super().inspect_native_row(row)
        assert 1 <= len(row['attempts']) <= 2 and row['final'] == row['attempts'][-1]
        assert not (len(row['attempts']) == 2 and row['attempts'][0].get('joint'))
        assert all(not a.get('generation', {}).get('retrieved_cards') and
                   not a.get('generation', {}).get('cards') for a in row['attempts'])

    def decorate_row(self, row, cell):
        if row.get('preparation_blocked_reason'):
            raise ReplayStop('granularity_material_preparation_blocked:' + row['preparation_blocked_reason'])
        row.update(arm=cell['condition'], memory_level=cell['condition'], Q_sorting=False,
            levels_are_strictly_nested=False, code_implementation_verified=None)

    @staticmethod
    def selection_check(rows):
        selected, empty_violation = {}, False
        for row in rows:
            if row['condition'] == 'L0':
                empty_violation |= any(a.get('generation', {}).get('retrieved_cards') or
                    a.get('generation', {}).get('cards') for a in row['attempts'])
            else:
                trace = row['attempts'][0].get('retrieval_trace') or {}
                if trace.get('status') == 'completed' and 'pre_level_selected_ids' in trace:
                    selected[row['condition']] = trace['pre_level_selected_ids']
        values = list(selected.values())
        mismatch = any(v != values[0] for v in values[1:]) if values else False
        return {'status': 'different' if mismatch or empty_violation else 'passed' if len(selected) == 4 else 'incomplete_model_or_retrieval_measurement',
            'matched_memory_levels': sorted(selected), 'pre_level_selected_ids': values[0] if values else None,
            'L0_memory_violation': bool(empty_violation), 'Q_updates': 0, 'levels_are_strictly_nested': False}

    def validate_saved_rows(self, rows):
        super().validate_saved_rows(rows)
        grouped = {}
        for row in rows:
            grouped.setdefault((row['task_id'], row['repeat']), []).append(row)
        if any(self.selection_check(items)['status'] == 'different' for items in grouped.values()):
            raise ReplayStop('saved_granularity_first_selection_or_L0_mismatch')

    def after_group(self, rows, check):
        result = self.selection_check(rows)
        self.io.save(f'shared_selection_checks/{rows[0]["task_id"]}_r{rows[0]["repeat"]}', result)
        if result['status'] == 'different':
            self.io.stop('granularity_first_selection_or_L0_mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'launch', 'run', 'resume', 'replay'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    FrozenGranularity.worker_limit = args.workers
    if args.action == 'prepare':
        value = prepare()
        print(json.dumps({'status': value.get('status', 'prepared_zero_API'), 'planned': value['planned_P7'], 'dependencies': dependencies()}))
        return
    dep = dependencies()
    if args.action == 'check':
        print(json.dumps(dep))
        return
    if args.action != 'replay' and not dep['ready']:
        raise ReplayStop('FG_LABELS_not_ready:' + ','.join(dep['reasons']))
    index = package_root()/'execution_index.json'
    sources = [Path(p) for p in base.read(index)['segments']] if index.exists() else []
    if args.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(base.wiring.SETTINGS['model'])
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_reduced_20261028.granularity run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
        if actual.stdout.strip():
            print(json.dumps({'status': 'already_running'}))
            return
        with (package_root()/'stdout.log').open('a', encoding='utf-8') as stdout, (package_root()/'stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_reduced_20261028.granularity', 'run', '--workers', str(args.workers)], cwd=base.ROOT,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(package_root()/'launch.json', {'pid': process.pid, 'started_utc': base.now()})
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
        return
    if args.action == 'replay':
        if not sources or base.read(sources[-1]/'summary.json').get('completed') != prepare()['planned_P7']:
            raise ReplayStop('full_2730_completed_cells_required_for_FG_replay')
        target = package_root()/'zero_API_replay'
        if (target/'replay_result.json').exists():
            print(json.dumps(base.read(target/'replay_result.json')))
            return
        FrozenGranularity(sources, offline=True, destination=target).execute()
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
            study = FrozenGranularity(sources, destination=target)
            write_json(index, {'segments': list(map(str, sources)) + [str(target)]})
            study.execute()
            write_json(package_root()/'completion.json', {'status': 'awaiting_agent_analysis', 'planned': prepare()['planned_P7'],
                'updated_utc': base.now(), 'classifier_trained': False})
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
