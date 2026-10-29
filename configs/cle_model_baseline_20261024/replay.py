"""基准事件完整回放索引及逐次验证重放；模型/Embedding HTTP一律禁用。"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from methods.sct_trajectory.replay_journal import ReplayStop,write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--revalidate',action='store_true',help='实际重执行已保存的代码与原测试，不生成新代码')
    parser.add_argument('--limit',type=int,default=0,help='验证事件数量；0=全部')
    args=parser.parse_args();run=args.run_root.resolve()
    import urllib.request
    def blocked(*a,**k):raise ReplayStop('replay_network_disabled')
    urllib.request.urlopen=blocked
    timeline=[]
    for kind,pattern in [('LLM','journals/*/requests/*.json'),('Embedding','journals/*/embedding_requests/*.json'),
                         ('validation','validation_events/*/*.json')]:
        for p in sorted(run.glob(pattern)):
            d=json.loads(p.read_text(encoding='utf-8'))
            timeline.append({'kind':kind,'time':d.get('started_utc'),
                'path':str(p.relative_to(run)),'status':d.get('status','completed' if 'result' in d else 'unfinished')})
    timeline.sort(key=lambda r:(r['time'] or '',r['path']))
    write_json(run/'replay_index.json',{'events':timeline,'counts':dict(Counter(r['kind'] for r in timeline)),
        'network_calls':0,'scope':'all saved requests/responses, code, tests and memory evolution; no new generation'})
    if not args.revalidate:
        print(json.dumps({'events':len(timeline),'network_calls':0}));return
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.internal_checks import execute_checks
    from methods.sct_trajectory.run_plus_frozen_comparison import evaluate
    functions={'PLT_official':validate_and_state,'public_internal':execute_checks,'BasePlus_official':evaluate}
    results=[]
    events=[r for r in timeline if r['kind']=='validation']
    for event in events[:args.limit or None]:
        d=json.loads((run/event['path']).read_text(encoding='utf-8'))
        if 'result' not in d:
            results.append({'path':event['path'],'status':'unfinished_original_not_reconstructed'});continue
        result=functions[d['kind']](*d['args'],**d['kwargs'])
        results.append({'path':event['path'],'original':d['result'],'replayed':result})
    write_json(run/'validation_replay.json',{'network_calls':0,'results':results,
        'note':'Preserve both old and replayed evidence; environment-sensitive differences are not overwritten.'})


if __name__=='__main__':main()
