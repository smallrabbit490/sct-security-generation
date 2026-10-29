"""精确复用初析110，补齐同类TLS中断后的4题；旧记录原位保留。"""
import argparse
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from unittest.mock import patch

from .retrieval import ROOT, INITIALS, IDS, StudyExecution, SETTINGS, prepare_initial_analysis, initial_inputs, initial_sources, native
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

OUT = ROOT/'initial_recovery_20261029'
MODULE = 'configs.cle_nonq_supervised_20261029.retrieval_recover'


def factory(identity):
    from methods.sct_trajectory import run_closed_loop as provider
    return provider._requester(SETTINGS['model'],180,4096,1,thinking='disabled',max_attempts=1,
        stream=True,hard_timeout=300,gate_wait_timeout=600,
        endpoint='https://api.chatanywhere.org/v1/chat/completions')


def protocol():
    value = copy.deepcopy(native.prep.read(INITIALS/'protocol.json'))
    # 原5题不变；1次已授权网络补发从FR总预算内调剂，旧失败仍计入累计。
    value['budget_proposed']['total_physical_HTTP_attempts'] = 6
    value['transport_reissue'] = dict(original_preparation_cap=5, cumulative_preparation_cap=6,
        parent_cap_unchanged=True, authorization='2026-10-27同类网络补发授权；2026-10-29按原计划继续检索')
    return value


def probe():
    wire = sorted((INITIALS/'wire').glob('*.status.json'))
    statuses = [native.prep.read(p) for p in wire]
    if len(statuses) != 2 or statuses[0]['status'] != 'response_closed' or statuses[1]['status'] != 'transport_error' or statuses[1].get('http_status') is not None or statuses[1].get('reason_type') != 'SSLEOFError':
        raise ReplayStop('not_the_audited_initial_TLS_failure')
    pending = list((INITIALS/'journals/initial_156/requests').glob('*.json'))
    if len(pending) != 1 or native.prep.read(pending[0])['status'] == 'completed':
        raise ReplayStop('saved_response_requires_review')
    schedule = native.prep.read(INITIALS/'schedule.json')
    p = protocol(); p['paid_execution_enabled'] = False
    io = StudyExecution(OUT/('zero_API_prefix_'+str(time.time_ns())), p, schedule, client_factory=factory,
        physical_open=lambda *a,**k: (_ for _ in ()).throw(ReplayStop('offline_forbidden')),
        replay_source=INITIALS, fixed_eight=False)
    public = initial_inputs()
    first = prepare_initial_analysis({'task_description':public['110']},io.request_for('initial_110'))
    context = native.prep.read(ROOT/'contexts/110.json')
    if first != context['initial_analysis'] or context['public_contract_digest'] != native.prep.contract_digest(public['110']):
        raise ReplayStop('completed_initial_context_differs')
    try:
        prepare_initial_analysis({'task_description':public['156']},io.request_for('initial_156'))
    except ReplayStop as exc:
        if str(exc) != 'saved_request_unresolved_or_failed_do_not_resubmit:'+native.prep.read(pending[0])['identity']:
            raise
    else:
        raise ReplayStop('expected_missing_initial_boundary_not_reached')
    result = dict(status='passed', reused_initials=['110'], exact_missing_initial='156',
                  new_HTTP=0, original_failed_HTTP=1, parent_budget_unchanged=True)
    write_json(OUT/'prefix_result.json', result)
    return result


def run():
    if native.prep.read(OUT/'prefix_result.json')['status'] != 'passed':
        raise ReplayStop('zero_API_prefix_required')
    sources = initial_sources()
    if len(sources) != 1:
        raise ReplayStop('existing_recovery_requires_reconciliation')
    public = initial_inputs()
    target = OUT/'segment_001'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
    io = StudyExecution(target, protocol(), native.prep.read(INITIALS/'schedule.json'),
        client_factory=factory,physical_open=opener.open,live=True,fixed_eight=False,
        resume_sources=sources,protected_paths=[ROOT/'inputs/public_tasks.json'])
    write_json(OUT/'execution_index.json', dict(segments=[str(target)]))
    complete = []
    try:
        with io.physical_records():
            for tid in IDS:
                context = ROOT/f'contexts/{tid}.json'
                if context.exists():
                    saved = native.prep.read(context)
                    if saved['public_contract_digest'] != native.prep.contract_digest(public[tid]):
                        raise ReplayStop('public_context_mismatch')
                    complete.append(tid)
                    continue
                value = prepare_initial_analysis({'task_description':public[tid]},io.request_for('initial_'+tid))
                write_json(context,dict(task_id=tid,public_contract_digest=native.prep.contract_digest(public[tid]),
                    initial_analysis=value,source_file=str(INITIALS/'public_inputs.json'),source_repeat=1,
                    no_new_API=False,purpose='retrieval_only_public_initial'))
                complete.append(tid)
                io.save('summary',dict(status='running',completed=len(complete),task_ids=complete,budget=io.budget.snapshot()))
        io.save('summary',dict(status='completed',completed=5,task_ids=complete,
                              code_generations=0,Q_updates=0,budget=io.budget.snapshot()))
        io.save('state',dict(status='completed',completed=5))
    except BaseException as exc:
        io.save('state',dict(status='needs_technical_recovery',completed=len(complete),reason=str(exc)))
        raise


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['probe','launch','run']); a=p.parse_args()
    if a.action=='probe':
        with patch.object(socket.socket,'connect',side_effect=ReplayStop('offline_forbidden')):
            print(json.dumps(probe()))
    elif a.action=='run': run()
    else:
        from tools.cle_live_workbench.app import process_inventory, worker_processes
        processes=process_inventory()
        if any(MODULE+' run' in (v.get('CommandLine') or '') for v in processes):
            raise ReplayStop('existing_initial_recovery_process')
        if sum(v['workers'] for v in worker_processes(processes)) >= 4:
            raise ReplayStop('worker_capacity_full')
        if (OUT/'execution_index.json').exists(): raise ReplayStop('existing_recovery_requires_reconciliation')
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(SETTINGS['model'])
        command=[sys.executable,'-B','-X','utf8','-m',MODULE,'run']
        with (OUT/'stdout.log').open('a',encoding='utf-8') as out,(OUT/'stderr.log').open('a',encoding='utf-8') as err:
            child=subprocess.Popen(command,cwd=native.prep.ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(OUT/'launch.json',dict(pid=child.pid,command=command,workers=1))
        print(json.dumps(dict(status='launched',pid=child.pid)))


if __name__=='__main__': main()
