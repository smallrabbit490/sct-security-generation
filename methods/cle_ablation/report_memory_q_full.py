"""全D_grow学习的原生复核与精简归档，不访问模型或评价数据池。"""
from __future__ import annotations
import argparse
import csv
import json
import platform
import sys
from collections import Counter
from pathlib import Path

from methods.cle_ablation.audit_memory_q import check_run, read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write


def build(root, out):
    check=check_run(root)
    rows=read_rows(root/'rows.jsonl')
    events=read_rows(root/'memory_q_events.jsonl')
    nodes=read_rows(root/'frozen/m_star_q.jsonl')
    metadata=json.loads((root/'run_metadata.json').read_text(encoding='utf-8'))
    controls=json.loads((root/'reference_calibration.json').read_text(encoding='utf-8'))['tasks']
    by_control={c['task_id']:c for c in controls}
    families=json.loads((root/'q_family_support.json').read_text(encoding='utf-8'))
    for event in events:
        if not by_control[str(event['task_id'])]['reward_eligible']:
            assert event.get('reward') is None, 'invalid reference received Q reward'
    valid_events=[e for e in events if e.get('reward') is not None and e.get('invariant_id')]
    assert sum(n['q_visits'] for n in nodes)==len(valid_events)
    summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    summary.update(protocol=metadata['protocol'],artifact_role='D_grow learning only',
        format_check=check, costs=json.loads((root/'cost.json').read_text(encoding='utf-8')),
        reference_calibration={'total':len(controls),'joint':sum(c['reference_state']=='A' for c in controls),
            'reward_eligible':sum(c['reward_eligible'] for c in controls),
            'reward_eligible_families':len({c['family_id'] for c in controls if c['reward_eligible']}),
            'excluded':sum(not c['reward_eligible'] for c in controls),
            'reasons':dict(Counter(reason for c in controls for reason in c['exclusion_reasons']))},
        tasks=len(rows),families=len({r['family_id'] for r in rows}),
        memory_entries=len(nodes),raw_root=str(root),git_branch='fjy/cle-memory-q-batch2',
        git_commit=metadata['git_commit'],implementation_committed=False,
        environment={'python':sys.version.split()[0],'platform':platform.platform()},
        D_gate_evaluated=False,Base_Plus_evaluated=False,wall_seconds=metadata['wall_seconds'])
    summary['learning_funnel']={'attempted_tasks':len(rows),
        'reward_eligible_tasks':sum(c['reward_eligible'] for c in controls),
        'tasks_with_Q_credit':len({str(e['task_id']) for e in valid_events}),
        'families_with_Q_credit':len({e['family_id'] for e in valid_events}),
        'attempts_with_Q_credit':len({(str(e['task_id']),e['attempt']) for e in valid_events}),
        'card_updates':len(valid_events)}
    out.mkdir(parents=True,exist_ok=True)
    write(out/'summary.json',summary)
    positive=Counter(e['invariant_id'] for e in valid_events if e['reward']==1)
    negative=Counter(e['invariant_id'] for e in valid_events if e['reward']==-1)
    learned=[{'invariant_id':n['invariant_id'],'cwe':n['cwe'],'q_value':n['q_value'],
        'q_visits':n['q_visits'],'independent_families':len(families[n['invariant_id']]),
        'positive_updates':positive[n['invariant_id']],'negative_updates':negative[n['invariant_id']]}
        for n in nodes if n['q_visits']>0]
    write(out/'learned_q_values.json',{'values':learned,'full_bank':len(nodes)})
    fields=['task_id','family_id','cwe','functional','security','joint','first_joint','measured',
            'workflow_error','calls','prompt_tokens','completion_tokens','total_tokens','elapsed_seconds',
            'reward_eligible','reference_state','reward_exclusion']
    with (out/'task_scores.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for row in sorted(rows,key=lambda r:metadata['task_ids'].index(int(r['task_id']))):
            control=by_control[str(row['task_id'])]
            writer.writerow({'task_id':row['task_id'],'family_id':row['family_id'],'cwe':row['cwe'],
                **{k:row['final'][k] for k in ('functional','security','joint','measured')},
                'first_joint':row['attempts'][0]['joint'],'workflow_error':row['error_type'] or '',
                **{k:row['usage'][k] for k in ('calls','prompt_tokens','completion_tokens','total_tokens')},
                'elapsed_seconds':row['elapsed_seconds'],'reward_eligible':control['reward_eligible'],
                'reference_state':control['reference_state'],'reward_exclusion':';'.join(control['exclusion_reasons'])})
    write(root/'format_check.json',check)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=build(args.root,args.out)
    print(json.dumps({'tasks':report['tasks'],'families':report['families'],
                      'Q_learning':report['Q_learning'],'format_check':report['format_check']},ensure_ascii=False))
