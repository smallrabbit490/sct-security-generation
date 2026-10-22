"""零API复用D_gate与D_grow记录，统计真实Q学习覆盖；不修改卡库。"""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configs.cle_memory_q_full_gate_cap3_20261019.analyze import trace_of
from methods.cle_ablation.runner import load_memory
from methods.sct_trajectory.semantic_retrieval import card_embedding_text, MAX_CARD_CHARS

GATE = ROOT/'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v4'
GROW = ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT = ROOT/'results/curated/cle_q_coverage_20261019'
RAW = ROOT/'translation_work/diagnostics/20261019/cle_memory_q/coverage_analysis_v1'


def rows(path):
    # 原始代码可能包含U+2028；只按物理行读取JSONL。
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump_csv(path, values):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def state(node):
    if node.q_visits == 0:
        return 'unlearned'
    return 'positive' if node.q_value > 0 else 'negative' if node.q_value < 0 else 'learned_zero'


def ids(attempt, key):
    return [c['invariant_id'] for c in attempt.get('generation', {}).get(key, [])]


def summarize(counter, bank, placebo=None):
    total = sum(counter.values())
    result = {'occurrences': total, 'unique_cards': len(counter)}
    for label, nodes in [('real_history', bank), ('assigned_Q', placebo or bank)]:
        counts = Counter()
        for identifier, n in counter.items():
            counts[state(nodes[identifier])] += n
        learned = total - counts['unlearned']
        result[label] = dict(counts, learned=learned,
                             coverage=learned/total if total else None,
                             unique_learned=sum(nodes[i].q_visits > 0 for i in counter))
    return result


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    RAW.mkdir(exist_ok=True, parents=True)
    bank = {n.invariant_id: n for n in load_memory(GROW/'observe/frozen/m_star_q.jsonl')}
    placebo = {n.invariant_id: n for n in load_memory(GATE/'shuffled_input_memory.jsonl')}
    eligible = {i for i,n in bank.items() if n.status in {'active','provisional','consolidated'}
                and 'python' in n.language_leaves and len(card_embedding_text(n)) <= MAX_CARD_CHARS}
    support = read(GROW/'observe/q_family_support.json')
    buckets = defaultdict(Counter)
    distributions = defaultdict(Counter)
    quality = defaultdict(Counter)
    exposures = defaultdict(Counter)
    attempt_rows = []
    task_keys = set()
    for row in rows(GATE/'rows.jsonl'):
        arm, tid = row['arm'], str(row['task_id'])
        assert (tid, arm) not in task_keys
        task_keys.add((tid, arm))
        for index, attempt in enumerate(row['attempts']):
            trace = trace_of(attempt)
            candidates = trace.get('candidate_ids', [])
            presented = trace.get('presented_candidate_ids', candidates)
            selected = ids(attempt, 'retrieved_cards')
            adopted = ids(attempt, 'cards')
            assert len(selected) == len(set(selected)) <= 3
            assert set(adopted) <= set(selected)
            stages = {'candidates':candidates, 'presented':presented,
                      'presented_first3':presented[:3], 'selected':selected, 'adopted':adopted}
            item = {'task_id':tid, 'family_id':row['family_id'], 'cwe':row['cwe'],
                    'arm':arm, 'attempt':attempt['attempt'],
                    'retrieval_status':trace.get('status','unavailable'),
                    'final_attempt': index == len(row['attempts'])-1}
            for stage, identifiers in stages.items():
                for span in ['all_attempts'] + (['first_attempt'] if index == 0 else []):
                    buckets[arm, span, stage].update(identifiers)
                for identifier in identifiers:
                    exposures[identifier][arm+'_'+stage] += 1
                item[stage+'_total'] = len(identifiers)
                item[stage+'_learned'] = sum(bank[i].q_visits > 0 for i in identifiers)
                item[stage+'_positive'] = sum(state(bank[i]) == 'positive' for i in identifiers)
                item[stage+'_ids'] = '|'.join(identifiers)
            attempt_rows.append(item)
            if index == 0:
                quality[arm]['tasks'] += 1
                quality[arm]['trace_'+trace.get('status','unavailable')] += 1
                if trace.get('status') == 'completed':
                    distributions[arm][sum(bank[i].q_visits > 0 for i in selected)] += 1
                    quality[arm]['empty_selected'] += not selected
                    quality[arm]['nonempty_without_Q'] += bool(selected) and not any(bank[i].q_visits > 0 for i in selected)
    assert len(task_keys) == 1192
    gate = {}
    table = []
    for arm in ['Q0','Q1','Q2','Q3']:
        gate[arm] = {'first_selection_learned_count_distribution':dict(distributions[arm]),
                     'first_retrieval_quality':dict(quality[arm])}
        for span in ['first_attempt','all_attempts']:
            gate[arm][span] = {}
            for stage in ['candidates','presented','presented_first3','selected','adopted']:
                values = summarize(buckets[arm,span,stage], bank, placebo if arm == 'Q3' else None)
                gate[arm][span][stage] = values
                real, assigned = values['real_history'], values['assigned_Q']
                table.append(dict(arm=arm, span=span, stage=stage,
                    total=values['occurrences'], learned=real['learned'],
                    positive=real.get('positive',0), negative=real.get('negative',0),
                    unlearned=real.get('unlearned',0), coverage=real['coverage'],
                    unique_cards=values['unique_cards'], unique_learned=real['unique_learned'],
                    assigned_learned=assigned['learned'], assigned_coverage=assigned['coverage']))
    # 旧D_grow漏斗只用于发现学习机会；D_gate卡ID不进入选题/学习清单。
    controls = {str(t['task_id']):t for t in read(GROW/'reference_calibration.json')['tasks']}
    grow = defaultdict(set)
    grow_valid = defaultdict(set)
    task_candidates, task_scores, task_selected, task_adopted = {}, {}, {}, {}
    for row in rows(GROW/'observe/rows.jsonl'):
        tid = str(row['task_id'])
        for index, attempt in enumerate(row['attempts']):
            trace = trace_of(attempt)
            stages = {'candidates':trace.get('candidate_ids',[]),
                      'selected':ids(attempt,'retrieved_cards'), 'adopted':ids(attempt,'cards')}
            for stage, identifiers in stages.items():
                grow[stage].update(identifiers)
                if controls[tid]['reward_eligible']:
                    grow_valid[stage].update(identifiers)
            if index == 0 and controls[tid]['reward_eligible']:
                task_candidates[tid] = set(stages['candidates'])
                task_scores[tid] = {s['id']:s['cosine'] for s in trace.get('scores',[])}
                task_selected[tid] = set(stages['selected'])
                task_adopted[tid] = set(stages['adopted'])
    events = list(rows(GROW/'observe/memory_q_events.jsonl'))
    grow['credited'] = {e['invariant_id'] for e in events if e.get('invariant_id') and e.get('reward') is not None}
    learned = {i for i,n in bank.items() if n.q_visits > 0}
    assert grow['credited'] == learned
    valid_count = sum(e.get('invariant_id') is not None and e.get('reward') is not None for e in events)
    assert valid_count == sum(n.q_visits for n in bank.values())
    groups, inventory = Counter(), []
    for identifier, node in bank.items():
        if node.q_visits:
            reason = 'learned'
        elif identifier not in eligible:
            reason = 'not_eligible'
        elif identifier not in grow['candidates']:
            reason = 'not_recalled_in_recorded_grow'
        elif identifier not in grow['selected']:
            reason = 'recalled_never_selected'
        elif identifier not in grow['adopted']:
            reason = 'selected_never_adopted'
        else:
            reason = 'adopted_but_no_valid_credit'
        groups[reason] += 1
        inventory.append(dict(invariant_id=identifier, cwe=node.cwe, eligible=identifier in eligible,
            Q=node.q_value, visits=node.q_visits, feedback_families=len(support.get(identifier,[])),
            uncovered_reason=reason, grow_recalled=identifier in grow['candidates'],
            grow_valid_task_recalled=identifier in grow_valid['candidates'],
            grow_selected=identifier in grow['selected'], grow_adopted=identifier in grow['adopted'],
            **{key:exposures[identifier][key] for key in
               [a+'_'+s for a in ['Q0','Q1','Q2','Q3'] for s in ['candidates','selected','adopted']]}))
    by_cwe = {}
    for cwe in sorted({n.cwe for n in bank.values()}, key=int):
        subset={i for i,n in bank.items() if n.cwe==cwe}
        by_cwe[cwe]={'cards':len(subset), 'eligible':len(subset & eligible), 'learned':len(subset & learned),
                     'grow_recalled':len(subset & grow['candidates']),
                     'grow_valid_task_recalled':len(subset & grow_valid['candidates']),
                     'grow_tasks':sum(str(t['cwe'])==cwe for t in controls.values()),
                     'grow_reward_eligible_tasks':sum(str(t['cwe'])==cwe and t['reward_eligible'] for t in controls.values()),
                     'Q2_unlearned_selected_occurrences':sum(exposures[i]['Q2_selected'] for i in subset-learned),
                     'Q2_unlearned_adopted_occurrences':sum(exposures[i]['Q2_adopted'] for i in subset-learned)}
    for stage in ['selected','adopted']:
        used=set(buckets['Q2','all_attempts',stage])
        stage_learned=used & learned
        gate['Q2']['all_attempts'][stage]['learning_depth']={
            'unique_visits1':sum(bank[i].q_visits==1 for i in stage_learned),
            'unique_one_feedback_family':sum(len(support.get(i,[]))==1 for i in stage_learned),
            'occurrences_visits1':sum(buckets['Q2','all_attempts',stage][i] for i in stage_learned if bank[i].q_visits==1),
            'occurrences_one_feedback_family':sum(buckets['Q2','all_attempts',stage][i] for i in stage_learned if len(support.get(i,[]))==1)}
        unlearned = used-learned
        reachable = unlearned & grow_valid['candidates']
        gate['Q2']['all_attempts'][stage]['unlearned_overlap_with_recorded_valid_Dgrow']={
            'reachable_unique':len(reachable),
            'reachable_occurrences':sum(buckets['Q2','all_attempts',stage][i] for i in reachable),
            'not_recorded_reachable_unique':len(unlearned-reachable),
            'not_recorded_reachable_occurrences':sum(buckets['Q2','all_attempts',stage][i] for i in unlearned-reachable)}
    # 按D_grow未学习候选的增量覆盖选择12题探针，先定名单再看新结果。
    remaining = set(task_candidates)
    covered = set()
    schedule = []
    used_families = set()
    for position in range(12):
        options = [t for t in remaining if controls[t]['family_id'] not in used_families]
        if not options:
            break
        tid = min(options, key=lambda t:(-len(task_candidates[t]-learned-covered),t))
        new = task_candidates[tid]-learned-covered
        schedule.append(dict(position=position+1, task_id=tid, family_id=controls[tid]['family_id'],
            cwe=controls[tid]['cwe'], new_unlearned_candidates=len(new),
            target_ids='|'.join(sorted(task_candidates[tid]-learned)),
            role='D_grow-only learning probe proposal; not executed'))
        covered.update(new)
        used_families.add(controls[tid]['family_id'])
        remaining.remove(tid)
    opportunity=[]
    for tid in sorted(task_candidates):
        for identifier in sorted(task_candidates[tid]-learned):
            opportunity.append(dict(task_id=tid,family_id=controls[tid]['family_id'],
                cwe=controls[tid]['cwe'],invariant_id=identifier,cosine=task_scores[tid].get(identifier),
                formerly_selected=identifier in task_selected[tid],formerly_adopted=identifier in task_adopted[tid]))
    result={'operation':'R zero-API coverage analysis and T learning proposal only',
        'source_gate':str(GATE.relative_to(ROOT)), 'source_learning':str(GROW.relative_to(ROOT)),
        'bank':{'cards':len(bank),'eligible':len(eligible),'learned':len(learned),
                'learned_eligible':len(learned & eligible),'states':dict(Counter(state(n) for n in bank.values())),
                'visit_histogram':dict(Counter(n.q_visits for n in bank.values())),
                'family_histogram_learned':dict(Counter(len(support.get(i,[])) for i in learned)),
                'valid_card_updates':valid_count},
        'D_gate':gate, 'D_grow':{
            'tasks':len(controls),'reward_eligible_tasks':sum(t['reward_eligible'] for t in controls.values()),
            'unique_funnel':{k:len(v) for k,v in grow.items()},
            'reward_eligible_task_funnel':{k:len(v) for k,v in grow_valid.items()},
            'uncovered_reason_counts':dict(groups),
            'recorded_recall_learned':len(grow['candidates'] & learned),
            'recorded_reward_eligible_recall_learned':len(grow_valid['candidates'] & learned),
            'event_skip_counts':dict(Counter(e['skip_reason'] for e in events if e.get('skip_reason'))),
            'proposed_12_task_unlearned_candidate_union':len(covered)},
        'by_cwe':by_cwe,'API_calls':0,'Q_updates':0,
        'caveat':'Q3 assigned visits are permuted labels, not this card actual learning. Recall reachability is historical observed reachability, not a proof that other cards cannot be recalled.'}
    (OUT/'coverage_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    dump_csv(OUT/'gate_stage_coverage.csv',table)
    dump_csv(OUT/'card_coverage_inventory.csv',inventory)
    dump_csv(RAW/'gate_attempt_coverage.csv',attempt_rows)
    dump_csv(OUT/'proposed_grow_probe12.csv',schedule)
    dump_csv(RAW/'grow_unlearned_opportunities.csv',opportunity)
    print(json.dumps({'bank':result['bank'],'grow':result['D_grow'],
        'gate_Q2_first':gate['Q2']['first_attempt'],
        'gate_selected_all':{a:gate[a]['all_attempts']['selected'] for a in gate},
        'gate_first_distribution':{a:gate[a]['first_selection_learned_count_distribution'] for a in gate}},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
