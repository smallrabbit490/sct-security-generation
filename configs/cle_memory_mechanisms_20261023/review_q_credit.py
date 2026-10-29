"""D01：逐尝试复核Q账本，做公开绑定诊断；零API，不更新Q或旧成绩。"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .prepare import ROOT, ONLINE, OUT, read, write, write_csv
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.memory_q import reward_from_evidence

VERSION='cle-q-credit-observational-review-v2'


def records(path):
    with path.open(encoding='utf-8') as stream:
        for number,line in enumerate(stream,1):
            if line.strip():yield number,json.loads(line)


def state(attempt):
    if not attempt['measured']:return 'unmeasured'
    return ('F+' if attempt['functional'] else 'F-')+('S+' if attempt['security'] else 'S-')


def family_patterns(events):
    """区分同族反馈不一致与不同族方向相反；只是观察，不生成适用性标签。"""
    by_family=defaultdict(set)
    for event in events:
        by_family[event['family_id']].add(event['reward'])
    positive=sorted(f for f,signs in by_family.items() if signs=={1.0})
    negative=sorted(f for f,signs in by_family.items() if signs=={-1.0})
    mixed=sorted(f for f,signs in by_family.items() if len(signs)>1)
    return {'feedback_families':len(by_family),'positive_only_families':positive,
            'negative_only_families':negative,'mixed_families':mixed,
            'has_opposed_pure_families':bool(positive and negative)}


def join_events(rows,events,cards,source_families):
    """用实际注入cards关联奖励；失败检索的过期attempt trace不能冒充选入记录。"""
    attempts={}
    for row in rows:
        for attempt in row['attempts']:
            key=(row['pool'],str(row['task_id']),attempt['attempt'])
            if key in attempts:raise ValueError('duplicate_native_attempt')
            attempts[key]=(row,attempt)
    joined=[]
    seen=set()
    for event in events:
        if not event['credited']:continue
        key=(event['pool'],str(event['task_id']),event['attempt'])
        row,attempt=attempts[key]
        generation=attempt['generation']
        actual=[c['invariant_id'] for c in generation.get('cards',[])]
        selected=[c['invariant_id'] for c in generation.get('retrieved_cards',[])]
        identifier=event['invariant_id']
        event_key=(*key,identifier)
        if event_key in seen:raise ValueError('duplicate_credited_card_attempt')
        seen.add(event_key)
        if (identifier not in actual or not set(actual)<=set(selected)
                or not attempt['measured'] or not generation['workflow_completed']
                or not attempt['code'].strip()):
            raise ValueError('credit_without_native_adoption_or_measurement')
        expected=1.0 if attempt['functional'] and attempt['security'] else -1.0
        if event['reward']!=expected:raise ValueError('reward_state_mismatch')
        if row.get('shared_initial_error') or reward_from_evidence(
                attempt['validation']['evidence'],code=attempt['code'])!=expected:
            raise ValueError('credit_technical_evidence_ineligible')
        if abs(event['q_after']-(event['q_before']+.3*(expected-event['q_before'])))>1e-10:
            raise ValueError('q_update_formula_mismatch')
        source=str(cards[identifier]['source']['task_id'])
        joined.append({**event,'source_task_id':source,'source_family_id':source_families[source],
            'source_cwe':str(cards[identifier]['cwe']),'target_cwe':str(row['cwe']),
            'same_CWE':str(cards[identifier]['cwe'])==str(row['cwe']),
            'same_source_family':source_families[source]==row['family_id'],
            'F':attempt['functional'],'S':attempt['security'],'Joint':attempt['joint'],
            'FS_state':state(attempt),'actual_adopted_count':len(actual),
            'actual_adopted_ids':json.dumps(actual),'selected_ids':json.dumps(selected),
            'source_row':row['_source_row'],'event_source':event['_event_source'],
            'implementation_review':'not_reviewed; reward is whole-attempt outcome'})
    return attempts,joined


def attempt_statistics(attempts,joined):
    credited=defaultdict(list)
    for event in joined:
        credited[event['pool'],str(event['task_id']),event['attempt']].append(event)
    states=Counter();sizes=Counter();duplicate=[]
    for key,events in credited.items():
        states[events[0]['FS_state']]+=1
        sizes[len(events)]+=1
    by_task=defaultdict(list)
    for key,(row,attempt) in attempts.items():by_task[key[:2]].append(attempt)
    for (pool,tid),items in by_task.items():
        items.sort(key=lambda a:a['attempt'])
        for previous,current in zip(items,items[1:]):
            if previous['code'].strip() and previous['code']==current['code']:
                before=credited.get((pool,tid,previous['attempt']),[])
                after=credited.get((pool,tid,current['attempt']),[])
                repeated={e['invariant_id'] for e in before}&{e['invariant_id'] for e in after}
                duplicate.append({'pool':pool,'task_id':tid,'before':previous['attempt'],
                    'after':current['attempt'],'before_state':state(previous),'after_state':state(current),
                    'recredited_ids':json.dumps(sorted(repeated)),
                    'repeat_negative_updates':sum(e['reward']==-1 and e['invariant_id'] in repeated for e in after)})
    return {'native_tasks':len(by_task),'native_attempts':len(attempts),
        'credited_attempts':len(credited),'credited_tasks':len({k[:2] for k in credited}),
        'credited_attempts_by_FS':dict(states),'credited_attempts_by_adopted_count':dict(sizes),
        'multi_card_credited_attempts':sum(n for size,n in sizes.items() if size>1),
        'exact_repeat_code_pairs':len(duplicate),
        'negative_reupdates_on_identical_code':sum(x['repeat_negative_updates'] for x in duplicate)},duplicate


PUBLIC_DIAGNOSTICS={
 '1003':{'prefix':"USER_POST_FORMAT = 'PUBLIC[{username}|{post_title}|{post_body}|{tags_html}]'\n",
         'check':"assert candidate('u', 't', 'b', ['tag']) == 'PUBLIC[u|t|b|<span>tag</span>]'",
         'purpose':'Preserve the supplied external template and tag markup'},
 '642':{'prefix':"ALLOWED_DOMAINS = ['trusted.example']\n",
        'check':"assert candidate('https://app.example/', 'https://trusted.example/welcome') == 'https://trusted.example/welcome'",
        'purpose':'Preserve the supplied approved external redirect domain'},
 '1363':{'prefix':"USERS = {1: 'admin', 2: 'user'}\nUSER_PROFILES = {2: {'name': 'Public example'}}\n",
         'check':"assert candidate(1, 2) == {'name': 'Public example'}",
         'purpose':'Allow the admin to view a supplied user profile'},
}


def public_binding_diagnostics(destination):
    """仅用公开允许的示例对象，先提供绑定再执行原代码；不读隐藏测试或标准答案。"""
    results=[]
    for tid,example in PUBLIC_DIAGNOSTICS.items():
        pair=read(OUT/'paired_code_evidence'/f'{tid}.json')
        for side in ('old','new'):
            suite={'source':'self_generated_internal','cases':[{
                'id':'external_binding','kind':'functional','purpose':example['purpose'],'code':example['check']}]}
            result=execute_checks(example['prefix']+pair[side]['code'],
                                  pair['public_task']['function_name'],suite)
            results.append({'task_id':tid,'side':side,'entry':pair['public_task']['function_name'],
                'source':pair[side+'_source'],'public_example':example,'result':result,
                'original_official_FSJ':{k:pair[side][k] for k in ('F','S','Joint')},
                'is_official_score':False,'target_reference_used':False})
    write(destination/'public_binding_diagnostics.json',results)
    return results


def main():
    destination=OUT/'q_credit_review_v2'
    destination.mkdir(exist_ok=False)
    cards={node['invariant_id']:node for _,node in records(ONLINE/'D_grow/frozen/m_star_q.jsonl')}
    source_families={tid:task['family_id'] for tid,task in read(ONLINE/'tasks_D_init.json').items()}
    rows=[];events=[]
    for pool in ('D_init','D_grow'):
        path=ONLINE/pool/'rows.jsonl'
        for number,row in records(path):
            rows.append({**row,'_source_row':str(path.relative_to(ROOT))+':'+str(number)})
        path=ONLINE/pool/'memory_q_events.jsonl'
        for number,event in records(path):
            events.append({**event,'_event_source':str(path.relative_to(ROOT))+':'+str(number)})
    attempts,joined=join_events(rows,events,cards,source_families)
    stats,duplicates=attempt_statistics(attempts,joined)
    by_card=defaultdict(list)
    for event in joined:by_card[event['invariant_id']].append(event)
    family_rows=[]
    for identifier,feedback in by_card.items():
        pattern=family_patterns(feedback)
        same_cwe=family_patterns([e for e in feedback if e['same_CWE']])
        source_family=feedback[0]['source_family_id']
        family_rows.append({'card_id':identifier,'source_task_id':str(cards[identifier]['source']['task_id']),
            'events':len(feedback),'positive_events':sum(e['reward']>0 for e in feedback),
            'negative_events':sum(e['reward']<0 for e in feedback),**pattern,
            'same_CWE_has_opposed_pure_families':same_cwe['has_opposed_pure_families'],
            'same_CWE_source_positive_other_negative':source_family in same_cwe['positive_only_families']
                and bool(set(same_cwe['negative_only_families'])-{source_family}),
            'same_CWE_source_negative_other_positive':source_family in same_cwe['negative_only_families']
                and bool(set(same_cwe['positive_only_families'])-{source_family})})
    cross=Counter()
    for event in joined:
        cross[('source_family' if event['same_source_family'] else 'other_family')+'_'+event['FS_state']]+=1
    stats.update(protocol=VERSION,credited_card_events=len(joined),
        all_recorded_events=len(events),skip_reasons=dict(Counter(e['skip_reason'] for e in events if not e['credited'])),
        card_events_by_FS=dict(Counter(e['FS_state'] for e in joined)),cross_family_event_FS=dict(cross),
        cards_in_current_feedback=len(by_card),
        cards_with_mixed_outcomes_within_a_family=sum(bool(r['mixed_families']) for r in family_rows),
        cards_with_opposed_pure_families=sum(r['has_opposed_pure_families'] for r in family_rows),
        cards_with_opposed_pure_families_same_CWE=sum(r['same_CWE_has_opposed_pure_families'] for r in family_rows),
        cards_source_positive_other_negative_same_CWE=sum(r['same_CWE_source_positive_other_negative'] for r in family_rows),
        cards_source_negative_other_positive_same_CWE=sum(r['same_CWE_source_negative_other_positive'] for r in family_rows),
        same_CWE_credit_events=sum(e['same_CWE'] for e in joined),
        newly_visited_cards_in_current_stages=sum(feedback[0]['q_visits']==1 for feedback in by_card.values()),
        already_visited_cards_in_current_stages=sum(feedback[0]['q_visits']>1 for feedback in by_card.values()),
        API_calls=0,Q_updates=0,official_scores_changed=False,
        full_historical_Q_ledger_complete=False,causal_claim_supported=False)
    initial_path=ROOT/'translation_work/diagnostics/20261020/cle_dinit_card_cap_v2/Lall/all_feedback/frozen/m_star_q.jsonl'
    initial={node['invariant_id']:node for _,node in records(initial_path)}
    if any(abs(initial[i]['q_value']-feedback[0]['q_before'])>1e-10
           or abs(cards[i]['q_value']-feedback[-1]['q_after'])>1e-10
           for i,feedback in by_card.items()):
        raise ValueError('current_stage_Q_endpoints_mismatch')
    stats.update(initial_snapshot=str(initial_path.relative_to(ROOT)),
        initial_visited_cards=sum(n['q_visits']>0 for n in initial.values()),
        current_visited_cards=sum(n['q_visits']>0 for n in cards.values()),
        initial_to_current_Q_endpoints_match=len(by_card),
        full_history_before_initial_snapshot_reconstructed=False)
    write_csv(destination/'q_credit_cases.csv',joined)
    write_csv(destination/'identical_code_recredit.csv',duplicates)
    write(destination/'card_family_reward_patterns.json',family_rows)
    examples=public_binding_diagnostics(destination)
    stats['public_binding_diagnostic_cases']=[{'task_id':r['task_id'],'side':r['side'],
        'passed':r['result']['passed'],'measured':r['result']['measured_count']} for r in examples]
    rescue=read(OUT/'paired_code_evidence/1113.json')
    stats['reviewed_rescue_without_new_declared_adoption']={
        'task_id':'1113','new_first_attempt':rescue['new']['attempt'],
        'new_adopted_ids':rescue['new']['adopted_ids'],'new_Joint':rescue['new']['Joint'],
        'claim':'rescue lacks an accepted-card path; not attributable to Q from scores alone'}
    write(destination/'summary.json',stats)
    write(ROOT/'results/curated/cle_memory_mechanisms_20261023/q_credit_review.json',stats)
    print(json.dumps(stats,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
