"""检索两题前缀接续：一次性传输缺失显式保留，不重复调用该题卡对。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import shutil
import subprocess
import sys
from unittest.mock import patch

from .retrieval_prefix import IDS
from .retrieval import ROOT, native, cumulative_initial_budget
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE='configs.cle_nonq_supervised_20261029.retrieval_continue'
AUDIT=ROOT/'two_task_prefix_20261029/transport_missing.json'


def audit():
    pairs={p['pair_id']:p for p in native.prep.read(ROOT/'blind_pairs.json')}
    mapping={p['pair_id']:str(p['task_id']) for p in native.prep.read(ROOT/'private_pair_mapping.json')}
    missing=native.prep.read(AUDIT) if AUDIT.exists() else {}
    checked=[]
    for item in native.unresolved(native.segments()):
        path=Path(item['path']); record=native.prep.read(path)
        pair_id=path.parent.parent.name.removeprefix('label_')
        if pair_id not in pairs or mapping[pair_id] not in IDS:
            raise ReplayStop('unresolved_is_not_a_prefix_label')
        prompt=native.prep.model_judge_prompt({k:pairs[pair_id][k] for k in ('task','card')})
        if record['prompt'] != prompt or record['settings']['model'] != native.MODEL:
            raise ReplayStop('label_request_does_not_match_frozen_pair')
        segment=path.parents[3]; matching=[]
        for wire in (segment/'wire').glob('*.request.json'):
            request=native.prep.read(wire);body=request['body']
            if isinstance(body,str): body=json.loads(body)
            if body.get('messages') == [{'role':'user','content':prompt}] and body.get('model')==native.MODEL:
                status=native.prep.read(wire.with_name(wire.name.replace('.request.json','.status.json')))
                matching.append(status)
        if len(matching)!=1 or matching[0].get('http_status') is not None or matching[0].get('status')!='transport_error' or matching[0].get('reason_type') not in ('SSLEOFError','RemoteDisconnected','TimeoutError','URLError','ConnectionResetError'):
            raise ReplayStop('not_a_single_unreturned_network_attempt')
        missing[pair_id]=dict(pair_id=pair_id,label=None,task_evidence='',card_evidence='',
            reason='一次物理调用后网络断开，缺失；不解释为不适用，不重发。',source='transport_missing',
            error_type='transport_missing_unmeasured',request_file=str(path))
        checked.append(str(path))
    write_json(AUDIT,missing)
    result=dict(status='passed',checked_unresolved=checked,missing_pairs=len(missing),
                reused_labels=len(native.saved_labels(native.segments())),new_HTTP=0,
                no_pair_reissue=True,Q_updates=0)
    write_json(AUDIT.with_name('continuation_check.json'),result)
    return missing


@contextmanager
def reconciliation(missing):
    old_unresolved,old_saved,old_label=native.unresolved,native.saved_labels,native.RetrievalExecution.one_label
    old_init=native.RetrievalExecution.__init__
    def initialize(worker,*args,**kwargs):
        old_init(worker,*args,**kwargs)
        shutil.copy2(__file__,worker.root/'continuation_entry.py')
    def pending(sources):
        return [v for v in old_unresolved(sources) if not any(v['path']==m['request_file'] for m in missing.values())]
    def saved(sources):
        values=old_saved(sources)
        if any(k in values and values[k].get('label') is not None for k in missing):
            raise ReplayStop('successful_label_exists_for_missing_pair')
        return {**missing,**values}
    mapping={p['pair_id']:str(p['task_id']) for p in native.prep.read(ROOT/'private_pair_mapping.json')}
    def bounded(worker,pair):
        if mapping[pair['pair_id']] not in IDS:return None
        return old_label(worker,pair)
    with patch.object(native,'unresolved',pending),patch.object(native,'saved_labels',saved),patch.object(native.RetrievalExecution,'one_label',bounded),patch.object(native.RetrievalExecution,'__init__',initialize):
        yield


def run():
    missing=audit()
    with reconciliation(missing),verified_proxy_transport(),cumulative_initial_budget():
        result=native.coordinate(resume=True)
    segment=native.segments()[-1]
    for key,value in missing.items(): write_json(segment/'labels'/f'{key}.json',value)
    result.update(AI_label_task_scope=sorted(IDS),missing_pairs_retained=len(missing),
                  no_missing_pair_redispatch=True)
    if result['status']=='awaiting_human_confirmation':result['status']='prefix_two_task_labels_complete'
    write_json(segment/'summary.json',result)
    labels=native.saved_labels(native.segments())
    expected={p['pair_id'] for p in native.prep.read(ROOT/'private_pair_mapping.json') if str(p['task_id']) in IDS}
    report=dict(status='completed_prefix_pending_review' if expected <= labels.keys() else 'incomplete',
        task_ids=sorted(IDS),candidate_pairs=len(expected),labeled_or_error_pairs=len(expected & labels.keys()),
        label_errors=sum(bool(labels[k].get('error_type')) for k in expected & labels.keys()),
        transport_missing=sum(labels[k].get('source')=='transport_missing' for k in expected & labels.keys()),
        new_AI_outside_prefix=False,shared_embedding_scope=57,human_confirmed=0,source_segment=str(segment))
    write_json(ROOT/'two_task_prefix_20261029/summary.json',report)
    print(json.dumps(report))


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','launch','run']);a=p.parse_args()
    if a.action=='check':
        with patch.object(socket.socket,'connect',side_effect=ReplayStop('offline_forbidden')):
            audit()
        print(json.dumps(native.prep.read(AUDIT.with_name('continuation_check.json'))))
    elif a.action=='run':run()
    else:
        from tools.cle_live_workbench.app import process_inventory,worker_processes
        processes=process_inventory()
        if any('configs.cle_nonq_supervised_20261029.retrieval_' in (v.get('CommandLine') or '') and ' run' in v.get('CommandLine','') for v in processes):
            raise ReplayStop('existing_retrieval_process')
        if sum(v['workers'] for v in worker_processes(processes))>=4:raise ReplayStop('worker_capacity_full')
        command=[sys.executable,'-B','-X','utf8','-m',MODULE,'run']
        folder=AUDIT.parent
        with (folder/'continue.stdout.log').open('a',encoding='utf-8') as out,(folder/'continue.stderr.log').open('a',encoding='utf-8') as err:
            child=subprocess.Popen(command,cwd=native.prep.ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(folder/'continue_launch.json',dict(pid=child.pid,command=command,workers=1))
        print(json.dumps(dict(status='launched',pid=child.pid)))


if __name__=='__main__':main()
