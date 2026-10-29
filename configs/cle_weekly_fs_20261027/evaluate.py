"""FFS全D_gate五条件：共享首次选卡，仅改变经验呈现，Q及正文冻结。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import threading

from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_v41_completion_20261026.materials import Materials
from methods.cle_ablation.run_memory_view_probe import ViewProvider
from methods.sct_trajectory.memory_views import source_projection, render_view
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

PROTOCOL = 'cle-weekly-full-function-security-views-20261027-v1'
CONDITIONS = ('B0', 'BM', 'BF', 'BS', 'BFS')
MEMORY_CONDITIONS = ('BM', 'BF', 'BS', 'BFS')
SEED = 20261027


def package_root():
    return base.RUN / 'FFS'


def source_hash(source):
    """与原Materials相同的来源序列化；保存64字符SHA-256，原缓存名用其前20字符。"""
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def schedule(ids, tasks):
    rng = random.Random(SEED)
    result = []
    for repeat in (1, 2):
        for tid in ids:
            arms = list(CONDITIONS)
            rng.shuffle(arms)
            result.extend({'cell_id': f'{tid}_r{repeat}_{arm}', 'task_id': tid,
                'family_id': tasks[tid]['family_id'], 'repeat': repeat, 'condition': arm,
                'pool': 'D_gate'} for arm in arms)
    return result


def legacy_catalog():
    """从已核对旧库重建实际A7/python投影，按完整source相等复用，不按卡ID猜测。"""
    inventory_file = package_root() / 'preflight_material_inventory.json'
    if not inventory_file.exists():
        return {}
    inventory = base.read(inventory_file)
    old_bank = Path(inventory['old_bank'])
    if not old_bank.is_absolute():
        old_bank = base.ROOT / old_bank
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.ablation import get_config
    engine = HskTreeRetriever(HskTree(), requester=lambda _: (_ for _ in ()).throw(ReplayStop('legacy_catalog_no_API')),
        ablation=get_config('A7'), retrieval_mode='semantic_llm')
    nodes = {node.invariant_id: node for node in base.runner.load_memory(old_bank)}
    catalog = {}
    for record in inventory['records']:
        if record.get('reusable') is not True:
            continue
        source = source_projection(engine._to_card({'language': 'python'}, nodes[record['card_id']], base=0., llm=None))
        identity = source_hash(source)
        if identity[:20] != record['cache_key']:
            raise ReplayStop('old_material_source_projection_changed:' + record['card_id'])
        path = Path(record['path'])
        if not path.is_absolute():
            path = base.ROOT / path
        spec = base.read(path)
        render_view(source, spec, 'BFS')
        catalog[identity] = {'source': source, 'spec': spec, 'path': str(path)}
    return catalog


class LockedMaterials(Materials):
    """同一个source的读、生成、保存串行；材料依原2次格式尝试和原字段fallback。"""

    def __init__(self, root, io, sources=(), offline=False):
        super().__init__(root, io.request_for)
        self.io, self.sources, self.offline = io, [Path(p) for p in sources], offline
        self.lock = threading.RLock()
        self.legacy = legacy_catalog()

    def view_specs(self, cards):
        with self.lock:
            result = {}
            for card in cards:
                source = source_projection(card)
                identity = source_hash(source)
                path = self.root / 'views' / (identity[:20] + '.json')
                origin = None
                if path.exists():
                    spec = base.read(path)
                    if spec.get('source_sha256') != identity or spec.get('source_projection') != source:
                        raise ReplayStop('local_material_cache_requires_exact_source_reconciliation')
                    origin = str(path)
                else:
                    saved = [p/'used_materials'/(identity+'.json') for p in reversed(self.sources)]
                    saved = next((p for p in saved if p.exists()), None)
                    if saved is not None:
                        evidence = base.read(saved)
                        if evidence['source_sha256'] != identity or evidence['source_projection'] != source:
                            raise ReplayStop('saved_material_source_mismatch')
                        spec, origin = evidence['spec'], str(saved)
                    elif identity in self.legacy and self.legacy[identity]['source'] == source:
                        evidence = self.legacy[identity]
                        spec, origin = copy.deepcopy(evidence['spec']), evidence['path']
                    else:
                        # 原Materials全部新请求经本包io，格式失败才使用其原有规则fallback。
                        spec = super().view_specs([card])[card['invariant_id']]
                        origin = 'new_source_only_annotation_in_current_package'
                render_view(source, spec, 'BFS')
                spec.update(source_sha256=identity, source_projection=source,
                    source_identity_scope='complete source_projection, including visible metadata',
                    semantic_roles_are_not_human_gold=True)
                write_json(path, spec)
                self.io.save('used_materials/'+identity, {'source_sha256': identity,
                    'source_projection': source, 'spec': spec, 'origin': origin,
                    'exact_coverage': 'passed', 'annotation_method': spec.get('annotation_method'),
                    'not_human_gold': True})
                result[card['invariant_id']] = spec
            return result


def prepare():
    inputs = package_root() / 'inputs'
    if (inputs / 'protocol.json').exists():
        return base.read(inputs / 'protocol.json')
    base.disk_check()
    source = base.RUN / 'FQ_GATE/inputs_v3/tasks.json'
    tasks = base.read(source)
    ids = base.read(base.RUN / 'manifest.json')['pools']['D_gate']
    if len(ids) != 298 or len(set(ids)) != 298 or set(ids) != set(tasks):
        raise ReplayStop('FFS_requires_full_298_v3_tasks')
    cells = schedule(ids, tasks)
    bank = str(base.RUN / 'shared_inputs/memory1939_q0.jsonl')
    # 材料最多1939来源，每来源最多2格式调用；原HTTP重试计入统一上界。
    protocol = {'protocol': PROTOCOL, 'package': 'FFS', 'planned_P7': 2980,
        'task_count': 298, 'card_count': 1939, 'repeats': 2, 'conditions': list(CONDITIONS),
        'bank_sources': {arm: bank for arm in CONDITIONS}, 'paid_execution_enabled': False,
        'model_settings': base.wiring.SETTINGS, 'max_cards': 3, 'max_repairs': 1, 'workers_max': 4,
        'Q_updates': 0, 'Q_sorting': False, 'new_cards': 0, 'first_initial_and_selection_shared_within': 'task x repeat; repeats independent',
        'first_retrieval': 'original CLE vector-plus-lexical candidate order and LLM terminal selection; no Q or threshold intervention',
        'first_injected_selected_IDs': 'BM/BF/BS/BFS identical before view transformation; B0 always empty',
        'repair': 'original P7 per-condition code and permitted feedback; original CLE retrieval for memory conditions; B0 empty',
        'material_provider': 'original Materials.view_specs wrapped by source-identity and serial cache lock',
        'material_annotation': 'source-only AI with exact character coverage, or original field-role fallback; not human semantic gold',
        'material_format_attempts_max': 2, 'material_cache_reuse': 'full source_projection equality plus SHA256 and exact coverage; never ID-only',
        'material_cache_inventory': str(package_root() / 'preflight_material_inventory.json'),
        'material_budget_max_source_cards': 1939, 'material_generation': 'only selected sources missing exact cache; not pre-generate all cards',
        'source_task_file': str(source), 'reference_preflight': str(base.RUN/'FQ_GATE/preflight_v3/summary.json'),
        'performance_gate_controls_dispatch': False, 'formal_historical_code_reuse': 0,
        'budget_proposed': {'conservative_model_and_embedding_tokens': 2980*150000 + 1939*100000,
            'total_physical_HTTP_attempts': 2980*40 + 1939*2*4,
            'embedding_HTTP_attempts_included_in_total': 2980*16},
        'budget_basis': 'code same bounded engineering cap; additional at most1939 sources x two format attempts x native four physical retries; no currency estimate',
        'resume_budget_reset': False, 'unknown_HTTP_redispatch': False}
    write_json(inputs/'tasks.json', tasks)
    write_json(inputs/'schedule.json', cells)
    write_json(inputs/'protocol.json', protocol)
    write_json(inputs/'reuse_manifest.json', {'formal_old_code_units': 0,
        'source_material_reuse': '116 current audited candidates, validated again on actual selected source; original annotation_method retained',
        'generation_reuse': 'only same exact completed cell or saved logical response; repeats independent',
        'new_material_calls': 'source-only missing selected sources; included in current package cost'})
    return protocol


def dependencies():
    reasons = []
    reference = base.RUN/'FQ_GATE/preflight_v3/summary.json'
    if not reference.exists():
        reasons.append('v3_reference_preflight_missing')
    else:
        value = base.read(reference)
        if (value.get('reference_joint') != 298 or value.get('reference_and_name_checks_passed') != 298
                or value.get('reference_preflight_ready') is not True):
            reasons.append('v3_reference_preflight_not_ready')
    source = base.RUN/'FQ_GATE/inputs_v3/tasks.json'
    copied = package_root()/'inputs/tasks.json'
    if not copied.exists() or not source.exists() or base.read(copied) != base.read(source):
        reasons.append('FFS_v3_task_snapshot_missing_or_different')
    inventory = package_root()/'preflight_material_inventory.json'
    if not inventory.exists() or not base.read(inventory).get('card_body_lifecycle_equal_excluding_Q_visits'):
        reasons.append('source_material_inventory_pending')
    gate = package_root()/'offline_checks.json'
    if not gate.exists() or base.read(gate).get('status') != 'passed':
        reasons.append('FFS_offline_checks_pending')
    return {'ready': not reasons, 'reasons': reasons, 'learning_or_K3_dependency': False,
            'real_dispatch_started_by_check': False}


class FrozenFS(base.FrozenRetest):
    conditions = CONDITIONS
    controlled_conditions = MEMORY_CONDITIONS
    reference_bank = 'BM'
    pool = 'D_gate'
    runner_module = 'configs.cle_weekly_fs_20261027.evaluate'

    def package_directory(self):
        return package_root()

    def policy(self, arm):
        return {'candidate_order': None, 'delta': None, 'record_arm': 'Q0', 'Q_checkpoint': None}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if any(node.q_value != 0 or node.q_visits != 0 for nodes in self.banks.values() for node in nodes):
            self.embedding._db.close()
            raise ReplayStop('FFS_requires_explicit_zero_Q_bank')
        root = self.out/'replay_material_cache' if self.offline else package_root()/'shared_materials'
        self.materials = LockedMaterials(root, self.io, self.sources, self.offline)

    def retrieve(self, query, request):
        from methods.sct_trajectory.retriever import HskTreeRetriever
        from methods.sct_trajectory.hsk_tree import HskTree
        from methods.sct_trajectory.ablation import get_config
        engine = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=self.embedding,
            semantic_delta=None, candidate_order=None)
        cards = engine.search(query, limit=3, pool_nodes=self.banks['BM'])
        return cards, engine.last_hier_trace

    def start(self, task, repeat):
        key = f'{task["index"]}_r{repeat}'
        for source in reversed(self.sources):
            path = source/'shared_starts'/(key+'.json')
            if path.exists():
                saved = base.read(path)
                if all(field in saved for field in ('query', 'selected_cards', 'retrieval_trace')):
                    self.io.save('shared_starts/'+key, saved)
                    return saved
        saved = super().start(task, repeat)
        public = base.runner.plt_contract(task)
        query = {**public, 'threat_analysis': saved['initial_analysis'], 'current_code': '', 'failure_evidence': {}}
        cards, trace = self.retrieve(query, self.io.request_for('shared_selection_'+key))
        if self.io.reason:
            raise ReplayStop(self.io.reason)
        saved.update(query=query, public_contract=public, selected_cards=cards, retrieval_trace=trace, repeat=repeat)
        self.io.save('shared_starts/'+key, saved)
        return saved

    def run_p7(self, cell, start, request):
        provider = ViewProvider(start, cell['condition'], lambda query: self.retrieve(query, request), self.materials.view_specs)
        return base.runner.run_one('PLT', self.tasks[cell['task_id']], 'P7', request, {'full': []},
            initial_analysis=copy.deepcopy(start['initial_analysis']), retrieval_provider=provider, max_experiences=3)

    def decorate_row(self, row, cell):
        row.update(arm=cell['condition'], view_arm=cell['condition'], Q_sorting=False,
            annotation_authority='source-only AI or original rule fallback; not human gold',
            code_implementation_verified=None)

    def inspect_native_row(self, row):
        if row['condition'] != 'B0':
            return super().inspect_native_row(row)
        # 原ViewProvider在B0修复轮不执行选择器，故其空轨迹没有selection_limit。
        # 保留原轨迹，直接核对P7尝试和无卡边界，不把它伪装成选卡完成。
        assert 1 <= len(row['attempts']) <= 2 and row['final'] == row['attempts'][-1]
        assert not (len(row['attempts']) == 2 and row['attempts'][0].get('joint'))
        assert all(not attempt.get('generation', {}).get('retrieved_cards') and
                   not attempt.get('generation', {}).get('cards') for attempt in row['attempts'])

    @staticmethod
    def view_selection_check(rows):
        groups = {}
        b0_violation = False
        for row in rows:
            attempt = row['attempts'][0]
            generation = attempt.get('generation', {})
            if row['condition'] == 'B0':
                b0_violation = b0_violation or any(a.get('generation', {}).get('retrieved_cards') or
                    a.get('generation', {}).get('cards') for a in row['attempts'])
            else:
                trace = attempt.get('retrieval_trace') or {}
                if trace.get('status') == 'completed' and 'pre_view_selected_ids' in trace:
                    groups[row['condition']] = trace['pre_view_selected_ids']
        selected = list(groups.values())
        mismatch = any(value != selected[0] for value in selected[1:]) if selected else False
        return {'status': 'different' if mismatch or b0_violation else 'passed' if len(groups) == 4 else 'incomplete_model_or_retrieval_measurement',
            'matched_memory_conditions': sorted(groups), 'pre_view_selected_ids': selected[0] if selected else None,
            'B0_memory_violation': b0_violation, 'Q_updates': 0}

    def validate_saved_rows(self, rows):
        super().validate_saved_rows(rows)
        grouped = {}
        for row in rows:
            grouped.setdefault((row['task_id'], row['repeat']), []).append(row)
        if any(self.view_selection_check(items)['status'] == 'different' for items in grouped.values()):
            raise ReplayStop('saved_FS_first_selection_or_B0_memory_mismatch')

    def after_group(self, rows, check):
        result = self.view_selection_check(rows)
        self.io.save(f'shared_selection_checks/{rows[0]["task_id"]}_r{rows[0]["repeat"]}', result)
        if result['status'] == 'different':
            self.io.stop('FS_first_selection_or_B0_memory_mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'launch', 'run', 'resume', 'replay'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    FrozenFS.worker_limit = args.workers
    if args.action == 'prepare':
        protocol = prepare()
        print(json.dumps({'status': 'prepared_zero_API', 'planned': protocol['planned_P7'], 'dependencies': dependencies()}))
        return
    dep = dependencies()
    if args.action == 'check':
        print(json.dumps(dep))
        return
    if args.action != 'replay' and not dep['ready']:
        raise ReplayStop('FFS_not_ready:' + ','.join(dep['reasons']))
    index = package_root()/'execution_index.json'
    sources = [Path(p) for p in base.read(index)['segments']] if index.exists() else []
    if args.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(base.wiring.SETTINGS['model'])
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_fs_20261027.evaluate run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
        if actual.stdout.strip():
            print(json.dumps({'status': 'already_running'}))
            return
        with (package_root()/'stdout.log').open('a', encoding='utf-8') as stdout, (package_root()/'stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_fs_20261027.evaluate', 'run', '--workers', str(args.workers)], cwd=base.ROOT, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(package_root()/'launch.json', {'pid': process.pid, 'started_utc': base.now()})
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
        return
    if args.action == 'replay':
        if not sources or base.read(sources[-1]/'summary.json').get('completed') != 2980:
            raise ReplayStop('full_2980_completed_cells_required_for_FFS_replay')
        target = package_root()/'zero_API_replay'
        if (target/'replay_result.json').exists():
            print(json.dumps(base.read(target/'replay_result.json')))
            return
        FrozenFS(sources, offline=True, destination=target).execute()
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
            destination = package_root()/f'segment_{len(sources)+1:03d}'
            study = FrozenFS(sources, destination=destination)
            write_json(index, {'segments': list(map(str, sources)) + [str(destination)]})
            study.execute()
            write_json(package_root()/'completion.json', {'status': 'awaiting_agent_analysis',
                'planned': 2980, 'updated_utc': base.now()})
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
