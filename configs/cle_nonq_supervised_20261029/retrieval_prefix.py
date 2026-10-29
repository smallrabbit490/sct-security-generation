"""57题检索测量的两题标注前缀；共享向量可准备57题，仅盲标固定两题。"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .retrieval import ROOT, INITIALS, native, cumulative_initial_budget, initial_summary

IDS = {'1184','500'}


def check():
    public=native.prep.read(ROOT/'inputs/public_tasks.json')
    assert len(public)==57 and IDS <= set(public)
    missing=[t for t in public if not (ROOT/'contexts'/f'{t}.json').exists()]
    return {'status':'waiting_initials' if missing else 'ready', 'prefix_task_ids':sorted(IDS),
        'parent_tasks':57,'missing_contexts':missing,'shared_embedding_scope':57,
        'new_AI_label_task_scope':2,'Q_updates':0,'code_generations':0,'new_HTTP':0}


def run():
    ready=check()
    if ready['status']!='ready':
        raise ReplayStop('first_initials_pending')
    if native.segments():
        raise ReplayStop('existing_prefix_requires_explicit_resume_review')
    first=initial_summary()
    if first['status']!='completed' or first['completed']!=5:
        raise ReplayStop('initial_preparation_not_complete')
    original=native.RetrievalExecution.one_label
    attribution={}
    skipped=set()
    def bounded(worker,pair):
        if not attribution:
            for item in native.prep.read(ROOT/'private_pair_mapping.json'):
                identity=item['pair_id'];tid=str(item['task_id'])
                if identity in attribution and attribution[identity]!=tid:
                    raise ReplayStop('ambiguous_pair_task_mapping')
                attribution[identity]=tid
        if pair['pair_id'] not in attribution:
            raise ReplayStop('unattributed_pair')
        if attribution[pair['pair_id']] not in IDS:
            skipped.add(pair['pair_id'])
            return None
        return original(worker,pair)
    with verified_proxy_transport(),cumulative_initial_budget(),patch.object(native.RetrievalExecution,'one_label',bounded):
        result=native.coordinate()
    segments=native.segments();segment=segments[-1]
    write_json(segment/'native_prefix_summary_before_scope_tag.json',result)
    result['status']='prefix_two_task_labels_complete' if result['status']=='awaiting_human_confirmation' else result['status']
    result['AI_label_task_scope']=sorted(IDS)
    result['shared_embedding_scope']=57
    result['other_task_pairs_not_labeled']=len(skipped)
    result['initial_preparation_budget_included']=True
    write_json(segment/'summary.json',result)
    write_json(segment/'state.json',{k:v for k,v in result.items() if k not in ('budget','logical')})
    expected={identity for identity,tid in attribution.items() if tid in IDS}
    labels=native.saved_labels(segments)
    labels.update({x['pair_id']:x for x in native.prep.read(ROOT/'reused_AI_labels.json')})
    report={'status':'completed_prefix_pending_review' if result['status']=='prefix_two_task_labels_complete' and expected<=set(labels) else 'incomplete',
        'task_ids':sorted(IDS),'candidate_pairs':len(expected),'labeled_or_error_pairs':len(expected & set(labels)),
        'label_errors':sum(bool(labels[k].get('error_type')) for k in expected & set(labels)),
        'new_AI_outside_prefix':False,'shared_embedding_scope':57,'human_confirmed':0,
        'source_segment':str(segment),'initial_preparation_in_same_parent_budget':True}
    write_json(ROOT/'two_task_prefix_20261029/summary.json',report)
    print(json.dumps(report))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['check','run'])
    a=p.parse_args()
    if a.action=='check':print(json.dumps(check()))
    else:run()


if __name__=='__main__':
    main()
