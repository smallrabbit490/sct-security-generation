"""从封存源码和逐次响应重放P3；任何未记录网络调用都立即停止。"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--stage',choices=['PLT','Base','Plus'],default='PLT')
    parser.add_argument('--limit',type=int,default=0,help='0=该集全部；仅控制本地回放，不触发新生成')
    parser.add_argument('--completed-only',action='store_true',help='仅回放原生rows中已交付的题，跳过中断任务')
    args=parser.parse_args();run=args.run_root.resolve();bundle=run/'source_bundle'
    sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'src'))
    from configs.cle_model_baseline_20261024.execute import install_recorders
    from methods.sct_trajectory.replay_journal import ReplayStop,write_json
    from methods.cle_ablation import runner
    import urllib.request
    def forbidden(*a,**k):raise ReplayStop('P3_replay_network_forbidden')
    urllib.request.urlopen=forbidden
    protocol=json.loads((run/'protocol.json').read_text(encoding='utf-8'))
    tasks=json.loads((run/f'inputs/tasks_{args.stage}.json').read_text(encoding='utf-8'))
    native=run/f'source_bundle/translation_work/nomemory/{args.stage}/rows.jsonl'
    old={r['task_id']:r for r in map(json.loads,native.read_text(encoding='utf-8').splitlines())}
    if args.completed_only:
        tasks=[t for t in tasks if (str(t['index']) if args.stage=='PLT' else f"{args.stage}:{t['ID']}") in old]
    tasks=tasks[:args.limit or None]
    install_recorders(run/'journals'/args.stage,'replay',Path(protocol['original_project_root']))
    runner.load_tasks=lambda dataset,limit:[(dataset,t) for t in tasks[:limit or None]]
    runner.POOLS=run/'inputs/pools.json'
    parent=bundle/'translation_work/replay'/args.stage
    parent.mkdir(parents=True,exist_ok=True)
    out=parent/f'pass_{len(list(parent.iterdir()))+1:03d}'
    sys.argv=['P3_replay','--dataset',args.stage,'--arms','P3','--out',str(out),
        '--model',protocol['model'],'--max-tokens','4096','--workers','4']
    runner.main()
    new=list(map(json.loads,(out/'rows.jsonl').read_text(encoding='utf-8').splitlines()))
    def view(row):
        return [{'code':a.get('code'),**{k:a.get(k) for k in ('functional','security','joint','measured')}}
                for a in row.get('attempts',[])]
    differences=[r['task_id'] for r in new if view(r)!=view(old[r['task_id']])]
    result={'stage':args.stage,'tasks':len(new),'API_calls':0,'credential_reads':0,
            'differing_task_ids':differences,'same_code_and_measurement':not differences,
            'output':str(out),'source':'saved model responses; native validators rerun locally'}
    write_json(out/'replay_check.json',result)
    write_json(run/f'replay_results/{args.stage}_{len(new)}.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
