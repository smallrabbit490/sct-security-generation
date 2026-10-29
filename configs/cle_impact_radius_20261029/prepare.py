"""从保存的无卡代码和L2已采用卡冻结IR02/IR03输入，不调用API。"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from methods.sct_trajectory.replay_journal import write_json

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN / 'impact_radius_20261028/prepare'
SOURCE = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion/C02_recovery_010/rows.jsonl'
SEED = '20261028-impact-radius-fixed-source'


def main():
    if (OUT / 'manifest.json').exists():
        raise RuntimeError('frozen_manifest_already_exists')
    tasks = json.loads((RUN / 'FG_LABELS/inputs_contract_v2/tasks.json').read_text(encoding='utf-8'))
    saved = {}
    with SOURCE.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['condition'] not in ('L0', 'L2'):
                continue
            first = row['attempts'][0]
            saved[str(row['task_id']), row['repeat'], row['condition']] = {
                'code': first['code'], 'cards': first['generation'].get('cards', []),
                'cell_id': row['cell_id'], 'family_id': row['family_id']}
    eligible, excluded = [], []
    for tid in sorted({key[0] for key in saved}, key=int):
        reason = []
        if tid not in tasks:
            reason.append('outside_current_growth_pool')
        for repeat in (1, 2):
            for level in ('L0', 'L2'):
                if (tid, repeat, level) not in saved:
                    reason.append('saved_input_missing')
            if not saved.get((tid, repeat, 'L0'), {}).get('code'):
                reason.append('empty_initial_code')
            if not saved.get((tid, repeat, 'L2'), {}).get('cards'):
                reason.append('no_saved_adopted_cards')
        if reason:
            excluded.append({'task_id': tid, 'reasons': sorted(set(reason))})
        else:
            eligible.append(tid)
    # 只用ID/CWE/family；不读取任何旧成绩进行选题。
    rank = lambda tid: hashlib.sha256((SEED + ':' + tid).encode()).hexdigest()
    pools = defaultdict(list)
    for tid in sorted(eligible, key=rank):
        pools[str(tasks[tid]['CWE_ID'])].append(tid)
    selected, families = [], set()
    while pools:
        for cwe in sorted(list(pools)):
            candidates = pools[cwe]
            tid = next((t for t in candidates if str(tasks[t]['family_id']) not in families), None)
            if tid:
                selected.append(tid); families.add(str(tasks[tid]['family_id'])); candidates.remove(tid)
            else:
                del pools[cwe]
    write_json(OUT / 'asset_inventory.json', {'source': str(SOURCE), 'eligible_tasks': eligible,
        'excluded': excluded, 'distinct_eligible_families': len(families), 'experiment_API': 0})
    if len(selected) < 36:
        raise RuntimeError('not_enough_saved_input_families_for_12_plus_24')
    manifest = {'status': 'inputs_frozen_pending_public_review_and_runner', 'seed': SEED,
        'IR02': selected[:12], 'IR03': selected[12:36], 'family_disjoint': True,
        'prior_exposure': 'C02 development/heldout tasks previously evaluated; method-development split only',
        'source_selection': 'L2 adopted cards both repeats present; no outcome-based filtering',
        'source_tasks': str(RUN / 'FG_LABELS/inputs_contract_v2/tasks.json'), 'source_rows': str(SOURCE)}
    for stage in ('IR02', 'IR03'):
        cells = []
        for tid in manifest[stage]:
            public = tasks[tid]['task_description']
            for repeat in (1, 2):
                initial = saved[tid, repeat, 'L0']
                card = saved[tid, repeat, 'L2']
                common = ('Edit the supplied Python code once using the public task and supplied experience. '
                    'Return only the complete Python code. Do not ask for test feedback.\n'
                    + 'PUBLIC TASK\n' + json.dumps(public, ensure_ascii=False)
                    + '\nSTARTING CODE\n' + initial['code']
                    + '\nEXPERIENCE\n' + json.dumps(card['cards'][:3], ensure_ascii=False))
                for arm in ('original_edit', 'boundary_edit'):
                    prompt = common
                    if arm == 'boundary_edit':
                        prompt += ('\nPreserve parameters, host-provided objects and configuration, return conventions, '
                            'and side effects that do not need to change for the specified security repair. '
                            'Do not substitute source-task example objects or values for those dependencies. '
                            'Change a boundary only when the public requirements explicitly require it.')
                    cells.append({'cell_id': f'{tid}_r{repeat}_{arm}', 'task_id': tid,
                        'family_id': str(tasks[tid]['family_id']), 'repeat': repeat, 'condition': arm,
                        'prompt': prompt, 'initial_cell': initial['cell_id'], 'card_cell': card['cell_id'],
                        'card_ids': [c['invariant_id'] for c in card['cards'][:3]],
                        'input_byte_upper_bound': len(prompt.encode('utf-8'))})
        write_json(OUT / stage / 'schedule.json', cells)
        write_json(OUT / stage / 'tasks.json', {t: tasks[t] for t in manifest[stage]})
        write_json(OUT / stage / 'budget.json', {'logical_edit_calls': len(cells),
            'output_tokens_cap': 4096 * len(cells),
            'input_utf8_byte_token_upper_bound': sum(c['input_byte_upper_bound'] for c in cells),
            'physical_HTTP_cap': 4 * len(cells), 'embedding_HTTP_cap': 0,
            'repair_calls': 0, 'currency_estimate': None, 'reset_on_resume': False})
    write_json(OUT / 'manifest.json', manifest)
    write_json(OUT / 'offline_checks.json', {'status': 'input_checks_passed_not_execution_ready',
        'tasks_IR02': 12, 'tasks_IR03': 24, 'independent_repeats': True,
        'family_overlap': [], 'only_prompt_delta': 'boundary instruction appended', 'new_HTTP': 0,
        'remaining': ['public contract sufficiency review', 'bounded dispatch and replay runner']})
    print(json.dumps({'eligible_tasks': len(eligible), 'distinct_families': len(families),
        'IR02_tasks': manifest['IR02'], 'IR03_count': len(manifest['IR03']), 'new_HTTP': 0}))


if __name__ == '__main__':
    main()
