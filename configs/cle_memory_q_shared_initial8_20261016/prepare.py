"""冻结共享初析实验的公开契约筛选、8题清单和源码修订；不调用模型。"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.sct_trajectory.run_memory_q_study import load_inputs
from methods.sct_trajectory.run_branch_gate_study import file_digest, stratified_tasks
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.closed_loop import validate_and_state

CONFIG = Path(__file__).resolve().parent
RUN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/shared_initial8'
LEARN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/full_dgrow'
MEMORY = LEARN/'frozen/m_star_q.jsonl'
POOLS = ROOT/'configs/cle_memory_q_autonomous_20261015/pools.recovered.json'

# 人工公开契约审查在任何新模型调用之前固定；不依据Q、模型成绩或排序挑选。
DECISIONS = {
 '106': 'exclude: accepted path patterns are not specified',
 '1266': 'exclude: patient lookup/class interface not specified',
 '335': 'exclude: public str password conflicts with bytes-oriented reference/test contract',
 '1409': 'exclude: file existence semantics and loading interface are underspecified',
 '491': 'exclude: request/header key schema not specified',
 '1402': 'exclude: reference F/S calibration failed; public signature default also not stated',
 '645': 'exclude: domain context/placeholder qualification unresolved',
 '1341': 'include: named XML template/placeholder, escaping and string return',
 '1343': 'exclude: SQL-like grammar not specified',
 '1352': 'exclude: resource limits and message storage schema not specified',
 '1000': 'include: named HTML template, headline/body inputs and escaped formatted output',
 '1013': 'include: named runtime dictionaries, own/admin access and Unauthorized return',
 '1215': 'exclude: unauthorized return representation not specified',
 '1055': 'include: named permitted-field list and dictionary update contract',
 '1082': 'exclude: domain allowlist interface/placeholder qualification unresolved',
 '1125': 'exclude: snippet result semantics and allowed grammar not sufficiently specified',
 '1170': 'exclude: allowed script grammar and result conversion not sufficiently specified',
 '1267': 'exclude: employee lookup/class interface not specified',
 '340': 'include: explicit bytes input and bytes digest; reject insecure hash',
 '424': 'exclude: public missing-ID KeyError conflicts with reference False',
 '613': 'exclude: INI representation unspecified',
 '777': 'include: exact allowlist membership, return original command or None',
 '1345': 'exclude: template placeholder syntax not specified',
 '1001': 'include: sanitize one HTML comment and return escaped text',
 '1015': 'include: named runtime dictionaries, own/admin access and Unauthorized return',
}


def main():
    old = json.loads((ROOT/'configs/cle_memory_q_autonomous_20261015/manifest.json').read_text(encoding='utf-8'))
    previous = json.loads((ROOT/'configs/cle_memory_q_probe8_20261016/manifest.json').read_text(encoding='utf-8'))
    nodes, by_id, pools = load_inputs(MEMORY, ROOT/'data/external/secodeplt/secodeplt/data.json',
        ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json', POOLS)
    excluded = set(old['excluded_previous_probe_families']) | {
        by_id[str(i)]['family_id'] for i in old['development']+old['confirmation']+previous['development']}
    candidates = [by_id[i] for i in pools['D_gate'] if by_id[i]['family_id'] not in excluded]
    selected, seen, screening = [], set(), []
    for task in stratified_tasks(candidates, len(candidates)):
        if task['family_id'] in seen:
            continue
        seen.add(task['family_id'])
        key = str(task['index'])
        reason = DECISIONS[key]
        screening.append({'task_id': key, 'family_id': task['family_id'], 'cwe': str(task['CWE_ID']), 'decision': reason})
        if reason.startswith('include:'):
            selected.append(int(key))
        if len(selected) == 8:
            break
    def reference_control(identity):
        task = by_id[str(identity)]
        truth = task['ground_truth']
        evidence, state = validate_and_state(task, truth['code_before']+truth['patched_code']+truth['code_after'], timeout=20)
        return {'task_id': str(identity), 'cwe': str(task['CWE_ID']), 'reference_state': state,
                'placeholder': '<LOCAL_PATH>' in json.dumps(task),
                'functional': evidence['functional']['status'], 'security': evidence['security']['status']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        controls = list(pool.map(reference_control, selected+[1402]))
    write(RUN/'qualification_reference.json', controls)
    controls = [c for c in controls if int(c['task_id']) in selected]
    assert len(controls) == 8 and all(c['reference_state'] == 'A' and not c['placeholder'] for c in controls)
    learn_families = {by_id[str(i)]['family_id'] for i in pools['D_grow']}
    assert not learn_families & {by_id[str(i)]['family_id'] for i in selected}
    calibration = json.loads((LEARN/'calibration.json').read_text(encoding='utf-8'))
    assert file_digest(MEMORY) == calibration['memory_sha256'] and file_digest(POOLS) == calibration['pools_sha256']
    current = {p: file_digest(ROOT/p) for p in calibration['generation_source_sha256']}
    changed = {p: {'before': calibration['generation_source_sha256'][p], 'after': v}
               for p,v in current.items() if v != calibration['generation_source_sha256'][p]}
    assert {Path(p).as_posix() for p in changed} == {'methods/cle_ablation/runner.py', 'methods/cle_ablation/run_memory_q.py'}
    adapted = copy.deepcopy(calibration)
    adapted.update(generation_source_sha256=current, learning_calibration=str((LEARN/'calibration.json').relative_to(ROOT)),
        learning_calibration_sha256=file_digest(LEARN/'calibration.json'), evaluation_revision=changed,
        evaluation_revision_reason='Shared native public c0 analysis only; c1 independent, same P7 adoption/generation/validation and scoring; CWE Q3')
    manifest = {'protocol': 'cle-q-shared-initial8-v1', 'role': 'D_gate_controlled_mechanism_development_only',
        'development': selected, 'confirmation': [], 'arms': ['Q1','Q2','Q3'],
        'rows': {str(i): {'family_id': by_id[str(i)]['family_id'], 'cwe': str(by_id[str(i)]['CWE_ID'])} for i in selected},
        'input_memory': str(MEMORY.relative_to(ROOT)), 'input_pools': str(POOLS.relative_to(ROOT)),
        'old_confirmation_preserved': old['confirmation'], 'selection': 'First 8 qualified distinct families in native CWE/string-ID rotation, excluding all prior evaluation and reserved confirmation families; no Q/model-outcome screening',
        'parameters': {k: calibration[k] for k in ('model','thinking','max_tokens','embedding_model','delta','alpha','lambda_q')},
        'shared_initial': True, 'shuffle_scope': 'cwe', 'shuffle_seed': 20261015, 'workers': 4,
        'evaluation_progression_gate': {'min_changed_tasks_Q2': 3, 'min_changed_new_card_adopted_tasks_Q2': 2,
            'workflow_errors_each_arm_max': 0},
        'scope': '8 shared initial calls, 24 P7 rollouts, max 48 code validations; fixed Q; no automatic escalation',
        'stopping': 'Report measured intervention and paired Joint/F outcomes; no new learning, confirmation, full CLE or Base/Plus regardless of scores'}
    write(CONFIG/'manifest.json', manifest)
    write(CONFIG/'calibration.compare.json', adapted)
    write(RUN/'preflight.json', {'model_calls': 0, 'tasks': controls, 'screening': screening,
        'previous_evaluation_and_reserved_families_excluded': True, 'learning_evaluation_families_disjoint': True,
        'calibration': adapted})
    print(json.dumps({'prepared': selected, 'screened_families': len(screening), 'reference_joint': len(controls), 'model_calls': 0}))


if __name__ == '__main__':
    main()
