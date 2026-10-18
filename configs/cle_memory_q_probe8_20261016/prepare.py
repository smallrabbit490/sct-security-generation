"""本轮8题三臂的零API准备；保留历史学习配置，仅登记已授权的编排器修改。"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from methods.cle_ablation.run_memory_q import shuffled_memory
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest
from methods.sct_trajectory.run_memory_q_study import load_inputs

CONFIG = Path(__file__).resolve().parent
RUN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle'
LEARN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/full_dgrow'
MEMORY = LEARN/'frozen/m_star_q.jsonl'
POOLS = ROOT/'configs/cle_memory_q_autonomous_20261015/pools.recovered.json'


def main():
    original = json.loads((ROOT/'configs/cle_memory_q_minimal_next_20261015/manifest.json').read_text(encoding='utf-8'))
    calibration = json.loads((LEARN/'calibration.json').read_text(encoding='utf-8'))
    assert file_digest(MEMORY) == calibration['memory_sha256']
    assert file_digest(POOLS) == calibration['pools_sha256']
    current = {path: file_digest(ROOT/path) for path in calibration['generation_source_sha256']}
    changed = [p for p, digest in current.items() if digest != calibration['generation_source_sha256'][p]]
    assert [Path(p).as_posix() for p in changed] == ['methods/cle_ablation/run_memory_q.py'], changed
    adapted = copy.deepcopy(calibration)
    adapted.update(generation_source_sha256=current,
        learning_calibration=str((LEARN/'calibration.json').relative_to(ROOT)),
        learning_calibration_sha256=file_digest(LEARN/'calibration.json'),
        evaluation_revision={p: {'before': calibration['generation_source_sha256'][p], 'after': current[p]} for p in changed},
        evaluation_revision_reason='Only comparison orchestration adds CWE-stratified Q3 and saves calibration; native P7 generation/validation unchanged')
    nodes, by_id, pools = load_inputs(MEMORY, ROOT/'data/external/secodeplt/secodeplt/data.json',
        ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json', POOLS)
    ids = original['development']
    tasks = [by_id[str(i)] for i in ids]
    assert len(tasks) == len({t['family_id'] for t in tasks}) == 8
    assert {str(i) for i in ids} <= set(pools['D_gate'])
    learn_rows = [json.loads(line) for line in (LEARN/'rows.jsonl').read_text(encoding='utf-8').splitlines()]
    assert not {t['family_id'] for t in tasks} & {r['family_id'] for r in learn_rows}

    def control(task):
        truth = task['ground_truth']
        evidence, state = validate_and_state(task, truth['code_before']+truth['patched_code']+truth['code_after'], timeout=20)
        return {'task_id': str(task['index']), 'family_id': task['family_id'], 'cwe': str(task['CWE_ID']),
                'reference_state': state, 'placeholder': '<LOCAL_PATH>' in json.dumps(task, ensure_ascii=False),
                'functional': evidence['functional']['status'], 'security': evidence['security']['status']}

    with ThreadPoolExecutor(max_workers=4) as pool:
        controls = list(pool.map(control, tasks))
    assert all(c['reference_state'] == 'A' and not c['placeholder'] for c in controls), controls
    placebo = shuffled_memory(nodes, 20261015, 'cwe')
    cwes = sorted({n.cwe for n in nodes})
    shuffle_check = {}
    for cwe in cwes:
        group = lambda bank: [n for n in bank if n.cwe == cwe]
        pairs = lambda bank: Counter((n.q_value, n.q_visits) for n in group(bank))
        assert pairs(nodes) == pairs(placebo)
        shuffle_check[cwe] = {'cards': len(group(nodes)), 'visited': sum(n.q_visits > 0 for n in group(nodes)),
            'changed_pairs': sum((a.q_value, a.q_visits) != (b.q_value, b.q_visits)
                                 for a, b in zip(group(nodes), group(placebo)))}
    manifest = {'protocol': 'cle-q-full-dgrow-probe8-cwe-shuffle-v1', 'role': 'D_gate_mechanism_development_only',
        'development': ids, 'confirmation': [], 'cwes': original['cwes'],
        'rows': {str(i): original['rows'][str(i)] for i in ids},
        'parameters': {**original['parameters'], 'delta': calibration['delta']},
        'arms': ['Q1', 'Q2', 'Q3'], 'input_memory': str(MEMORY.relative_to(ROOT)),
        'input_pools': str(POOLS.relative_to(ROOT)), 'learning_source': str(LEARN.relative_to(ROOT)),
        'selection': original['selection'], 'old_confirmation_preserved': original['old_confirmation_preserved'],
        'evaluation_progression_gate': original['evaluation_progression_gate'],
        'scope': '24 native P7 rollouts, maximum 48 generated-code validations; no learning or Base/Plus; no automatic escalation'}
    write(CONFIG/'manifest.json', manifest)
    write(CONFIG/'calibration.compare.json', adapted)
    RUN.mkdir(parents=True, exist_ok=True)
    write(RUN/'preflight.json', {'model_calls': 0, 'tasks': controls, 'shuffle_by_cwe': shuffle_check,
        'learning_evaluation_families_disjoint': True, 'calibration': adapted,
        'original_learning_calibration_unchanged': True})
    print(json.dumps({'status': 'prepared', 'tasks': ids, 'reference_joint': len(controls),
                      'visited_cards': sum(n.q_visits > 0 for n in nodes), 'shuffle_by_cwe': shuffle_check}))


if __name__ == '__main__':
    main()
