"""零API固定三池、公开契约、参考奖励资格和Q学习预算；原数据不修改。"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from methods.cle_ablation.run_memory_q_unlimited import inputs
from methods.cle_ablation.retrieval_q_study import reference_check
from methods.cle_ablation.runner import load_memory, plt_contract
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.run_memory_q_study import _write_memory

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / 'configs/cle_weekly_full_20261027'
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
PROTOCOL = 'cle-weekly-full-requirements-20261027-v1'
STAGES = [('K0', 'D_init'), ('K1', 'D_grow'), ('K2', 'D_grow'), ('K3', 'D_grow')]
MEMORY = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion/shared_inputs/memory1939.jsonl'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def disk_check():
    free = shutil.disk_usage(RUN.anchor).free
    if free < 5 * 1024**3:
        raise RuntimeError('E_drive_less_than_5GiB_no_dispatch')
    return free


def configure_validation():
    # 既有PLT夹具使用Git提供的shell工具；不更换验证后端。
    git_bin = r'C:\Program Files\Git\usr\bin'
    if git_bin not in os.environ.get('PATH', '').split(os.pathsep):
        os.environ['PATH'] = git_bin + os.pathsep + os.environ.get('PATH', '')


def prepare_inputs():
    disk_check()
    shared = RUN / 'shared_inputs'
    if (RUN / 'manifest.json').exists():
        return read(RUN / 'manifest.json')
    _, tasks, pools = inputs()
    # 延续原逐题学习顺序；后续三个D_grow轮次都按同一名单顺序。
    old_manifest = read(ROOT / 'configs/cle_q_online_20261020/manifest.json')
    manifest = {'protocol': PROTOCOL, 'pools': {}, 'family_overlap': {}, 'task_overlap': {}}
    sources = {}
    for pool, expected in [('D_init', 303), ('D_grow', 273), ('D_gate', 298)]:
        identifiers = list(map(str, old_manifest[pool]))
        assert len(identifiers) == len(set(identifiers)) == expected
        assert set(identifiers) == set(map(str, pools[pool]))
        manifest['pools'][pool] = identifiers
        for key in identifiers:
            sources[key] = ['original_PLT_and_existing_public_contract_overrides']
    overlays = [
        ('D_init', ROOT / 'configs/cle_dinit_full_learning_20261020_v4b/tasks.json'),
        ('D_grow', ROOT / 'configs/cle_dgrow_url_repair_20261019/repaired_tasks.json'),
        ('D_gate', ROOT / 'translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48_restored_urls_v2.json'),
    ]
    for pool, path in overlays:
        values = read(path)
        values = values.values() if isinstance(values, dict) else values
        for value in values:
            key = str(value['index'])
            assert key in manifest['pools'][pool]
            assert value['family_id'] == tasks[key]['family_id']
            tasks[key] = copy.deepcopy(value)
            sources[key].append(str(path.relative_to(ROOT)))
    for pool, identifiers in manifest['pools'].items():
        chosen = {key: tasks[key] for key in identifiers}
        write_json(shared / f'tasks_{pool}.json', chosen)
        write_json(shared / f'public_{pool}.json', {key: plt_contract(task) for key, task in chosen.items()})
    names = list(manifest['pools'])
    for i, left in enumerate(names):
        for right in names[i+1:]:
            key = left + '__' + right
            manifest['task_overlap'][key] = sorted(set(manifest['pools'][left]) & set(manifest['pools'][right]))
            manifest['family_overlap'][key] = sorted({tasks[k]['family_id'] for k in manifest['pools'][left]} &
                                                   {tasks[k]['family_id'] for k in manifest['pools'][right]})
            assert not manifest['task_overlap'][key] and not manifest['family_overlap'][key]
    bank = load_memory(MEMORY)
    assert len(bank) == 1939
    for card in bank:
        card.q_value = 0.0
        card.q_visits = 0
    shared.mkdir(parents=True, exist_ok=True)
    _write_memory(shared / 'memory1939_q0.jsonl', bank)
    manifest.update(task_sources=sources, family_by_task={key: tasks[key]['family_id'] for key in sources},
                    cwe_by_task={key: str(tasks[key]['CWE_ID']) for key in sources},
                    card_count=len(bank), original_card_source=str(MEMORY),
                    Q_initial=0, visits_initial=0, stages=[{'id': stage, 'pool': pool, 'count':len(manifest['pools'][pool])}
                                                        for stage, pool in STAGES])
    write_json(RUN / 'manifest.json', manifest)
    write_json(RUN / 'reuse_manifest.json', {'protocol': PROTOCOL, 'formal_old_code_units_reused': 0,
        'reason': 'new Q starts at zero; v4.1 learning and current public contracts need independent generated code',
        'embedding_cache_reuse': 'exact text/model SQLite cache only; no model response reuse across repeats',
        'historical_completed_run': '20261026:1376 code units and160 selection units, retained unchanged',
        'theoretical_internal_max': 1788, 'confirmed_internal_units': 0})
    return manifest


def qualification(manifest):
    configure_validation()
    all_tasks = {key: value for pool in manifest['pools'] for key, value in read(RUN/'shared_inputs'/f'tasks_{pool}.json').items()}
    folder = RUN / 'preflight' / 'tasks'
    def check(key):
        path = folder / f'{key}.json'
        if path.exists():
            return read(path)
        task = all_tasks[key]
        try:
            result = reference_check(task)
        except (SyntaxError, ValueError) as exc:
            result = {'task_id': key, 'passed': False, 'state': 'unmeasured',
                      'preflight_error': type(exc).__name__, 'undeclared_setup_bindings': []}
        placeholder = '<LOCAL_PATH>' in json.dumps(task, ensure_ascii=False)
        result.update(family_id=task['family_id'], cwe=str(task['CWE_ID']), placeholder=placeholder,
                      reward_eligible=bool(result['passed'] and not placeholder),
                      qualification_protocol=PROTOCOL,
                      evidence_scope='reference joint plus existing public setup-name check; not exhaustive semantic contract review')
        write_json(path, result)
        return result
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = [executor.submit(check, key) for key in all_tasks]
        for job in as_completed(jobs):
            result = job.result()
            results[result['task_id']] = result
            if len(results) % 50 == 0:
                print(json.dumps({'preflight_completed':len(results), 'planned':874}), flush=True)
    summary = {'protocol': PROTOCOL, 'tasks': results, 'pools': {}}
    for pool, identifiers in manifest['pools'].items():
        summary['pools'][pool] = {'planned': len(identifiers),
            'reward_eligible': sum(results[key]['reward_eligible'] for key in identifiers),
            'reference_joint': sum(results[key]['state']=='A' for key in identifiers),
            'ineligible_ids': [key for key in identifiers if not results[key]['reward_eligible']]}
    summary['historical_228_45_not_assumed'] = True
    write_json(RUN/'preflight/qualification.json', summary)
    return summary


def freeze(manifest, checks):
    # 既有全流程实测65,186,659 tokens/1376代码格仅作工程尺度，不作本轮费用。
    # 每P7预留150k tokens，40次物理HTTP含最多16次Embedding；累计不重置。
    # 原生2次生成，每次初析/选卡/复析/规划/生成约5次逻辑模型请求；物理重试亦扣预算。
    budgets = {'protocol': PROTOCOL, 'currency_cost': None, 'cache_hit_assumption': None,
        'basis': {'historical_tokens':65186659, 'historical_code_cells':1376,
                  'tokens_per_P7_cap':150000, 'physical_HTTP_per_P7_cap':40, 'embedding_HTTP_per_P7_cap':16},
        'stages': {stage:{'tokens':150000*len(manifest['pools'][pool]),
                         'HTTP':40*len(manifest['pools'][pool]),
                         'embedding_HTTP':16*len(manifest['pools'][pool])} for stage,pool in STAGES},
        'not_transferable_between_stages': True, 'reset_on_resume':False,
        'unknown_usage': 'reserve conservative request budget, never zero',
        'other_packages': 'pending native bound and runnable wiring; cannot dispatch using learning budget'}
    plan = read(CFG/'execution_plan.json')
    protocol = {'protocol': PROTOCOL, 'model':plan['model'], **plan['parameters'],
        'time_policy':plan['time_policy'], 'paid_execution_enabled':True,
        'retrieval_mode':'semantic_llm', 'candidate_order':'q', 'semantic_delta':-1,
        'embedding_model':'text-embedding-3-large', 'selector_max_tokens':256,
        'selector_max_chars':420000, 'candidate_vector_top_k':24, 'candidate_lexical_top_k':8,
        'update_boundary':'after each P7 task: c0 then c1 adopted eligible cards; next task reads updated Q',
        'card_text_and_lifecycle_frozen':True, 'new_cards':False,
        'all_tasks_executed_even_if_reference_ineligible':True,
        'reference_ineligible_rewards':None, 'performance_continuation_gate':False,
        'completed_first_two_are_part_of_full_manifest':True,
        'unknown_HTTP_may_not_be_redispatched':True,
        'public_contract_protocol':'original plus explicitly saved prior public repairs; per-task source in manifest',
        'run_root':str(RUN), 'Q_start':'fresh zero, not old972-feedback Q',
        'preflight_pools':checks['pools']}
    write_json(RUN/'budget.json', budgets)
    write_json(RUN/'protocol.json', protocol)
    write_json(RUN/'preflight/state.json', {'status':'inputs_qualified_pending_runner_tests',
        'completed_reference_checks':874, 'paid_dispatch_ready':False,
        'not_a_joint_result':True, 'other_packages_ready':False})
    for name in ('protocol.json', 'manifest.json', 'budget.json', 'reuse_manifest.json'):
        shutil.copy2(RUN/name, CFG/name)
    print(json.dumps({'prepared':True, 'qualification':checks['pools'], 'paid_dispatch_ready':False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare'])
    parser.parse_args()
    manifest = prepare_inputs()
    checks = qualification(manifest)
    freeze(manifest, checks)


if __name__ == '__main__':
    main()
