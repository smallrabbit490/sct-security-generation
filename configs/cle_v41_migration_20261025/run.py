"""S0/S1：同原生P7空卡/1939卡迁移；共享首次初析，只读经验，不学习Q。"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'src'))
from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop, write_json

RUN = ROOT / 'translation_work/diagnostics/20261025/cle_v41_migration_S1'
MODEL = 'deepseek-v4.1-flash-1017'
VERSION = 'cle-v41-native-P7-empty-vs-legacy1939-v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def now():
    return datetime.now(timezone.utc).isoformat()


def schedule(protocol):
    """技术2题的两个重复先完成；所有技术格计入12题48格，不增付费样本。"""
    rng = random.Random(20261025)
    pairs = []
    for group, tasks in [('technical', protocol['splits']['development'][:2]),
                         ('development', protocol['splits']['development'][2:])]:
        for repeat in (1, 2):
            for task in tasks:
                arms = ['E0', 'E1']; rng.shuffle(arms)
                pairs.append({**task, 'repeat': repeat, 'group': group, 'arms': arms,
                              'pair_id': f"{task['task_id']}_r{repeat}"})
    return pairs


def empty_provider(query):
    """仅关闭记忆输入；P7复析、规划、修复和原验证器仍全部执行。"""
    return [], {'status': 'completed', 'candidate_ids': [], 'selected_ids': [],
                'reason': 'E0_explicit_empty_memory_all_attempts', 'Q_enabled': False}


def technical_errors(row):
    errors = []
    for a in row['attempts']:
        if not a.get('measured'):
            errors.append(a.get('error_type') or 'unmeasured')
        g = a.get('generation', {})
        if not g.get('workflow_completed'):
            errors.append('workflow_incomplete')
        errors.extend(s['stage'] + ':' + s['status'] for s in g.get('stages', [])
                      if s['status'] not in ('completed', 'reused'))
        trace = a.get('retrieval_trace') or {}
        if trace.get('status') != 'completed':
            errors.append('retrieval_not_completed')
        if len(g.get('retrieved_cards') or []) > 3:
            errors.append('card_cap_exceeded')
        if row['migration_arm'] == 'E0' and (g.get('cards') or g.get('retrieved_cards')):
            errors.append('empty_arm_contains_memory')
    return errors


def prepare(run):
    """封存当前源码、明确题单和冻结库；没有任何网络/凭据访问。"""
    from methods.cle_ablation import runner
    from methods.cle_ablation.run_joint_contract import load_explicit_tasks
    if run.exists():
        raise RuntimeError('existing_run_not_overwritten')
    if shutil.disk_usage(ROOT).free < 10 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    p = read(ROOT / 'configs/cle_v41_migration_20261025/protocol.json')
    tasks = {str(t['index']): t for t in load_explicit_tasks(ROOT / p['task_source'], 'PLT')}
    ids = [t['task_id'] for t in p['splits']['development']]
    selected = [tasks[i] for i in ids]
    assert len(selected) == 12 and len({t['family_id'] for t in selected}) == 12
    nodes = runner.load_memory(ROOT / p['memory'])
    assert len(nodes) == 1939 and sum(n.q_visits > 0 for n in nodes) == 972
    p.update(protocol=VERSION, status='authorized_S0_S1_only', paid_execution_enabled=True,
             authorization='User 2026-10-25: S0, 2-task technical then12-task two-repeat E0/E1; no Q/classifier/BasePlus',
             original_project_root=str(ROOT), candidate_order=None, semantic_delta=None,
             Q_enabled=False, Q_updates_during_transfer=False, workers=4,
             counts={'technical_included':8, 'total_P7':48},
             initial_analysis='one native analysis_prompt per task/repeat; no old-model response reuse',
             max_http=2000, max_embedding_http=200, max_conservative_tokens=8_000_000,
             scope='S0 and S1 only; no validation24 or further packages',
             authorization_note='Current user explicitly authorized this S0/S1 package only.')
    run.mkdir(parents=True)
    write_json(run / 'protocol.json', p)
    write_json(run / 'inputs/tasks.json', selected)
    shutil.copy2(ROOT / p['memory'], run / 'inputs/memory.jsonl')
    write_json(run / 'schedule.json', schedule(p))
    manifest = {}
    for folder in ('methods', 'src', 'configs/cle_v41_migration_20261025',
                   'configs/cle_model_baseline_20261024'):
        for source in (ROOT / folder).rglob('*.py'):
            rel = source.relative_to(ROOT)
            dest = run / 'source_bundle' / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            manifest[str(rel)] = runner.digest(source)
    write_json(run / 'source_manifest.json', manifest)
    write_json(run / 'input_manifest.json', {'tasks':runner.digest(run/'inputs/tasks.json'),
          'memory':runner.digest(run/'inputs/memory.jsonl'), 'legacy_source':str(ROOT/p['memory']),
          'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()})
    # 只复用文本/模型/版本相同的静态向量；备份API确保WAL中的已提交缓存也包含。
    cache = ROOT / 'translation_work/cache/embeddings/cle.sqlite3'
    if cache.exists():
        import sqlite3
        with sqlite3.connect(f'file:{cache.as_posix()}?mode=ro', uri=True) as src:
            with sqlite3.connect(run / 'embeddings.sqlite3') as dst:
                src.backup(dst)
        shutil.copy2(run/'embeddings.sqlite3',run/'embedding_seed.sqlite3')
    write_json(run / 'state.json', {'status':'ready','pid':None,'completed_P7':0,'time':now()})
    print(json.dumps({'status':'ready','API_calls':0,'planned_P7':48,'run':str(run)}))


def summarize(run):
    parts=[run]+([Path(p) for p in read(run/'recovery_segments.json')] if (run/'recovery_segments.json').exists() else [])
    rows = [read(p) for base in parts for p in sorted((base/'task_rows').glob('*.json'))]
    if len({r['cell_id'] for r in rows})!=len(rows):raise RuntimeError('duplicate_completed_cell')
    result = {'protocol':VERSION,'model':MODEL,'planned_P7':48,'completed_P7':len(rows),
              'arms':{},'Q_updates':0,'card_generation':0,'time':now()}
    for arm in ('E0','E1'):
        items = [r for r in rows if r['migration_arm']==arm]
        stats = {'completed':len(items),'first':{},'final':{},'technical_errors':0,
                 'selected_card_occurrences':0,'adopted_card_occurrences':0,'rows_with_adoption':0}
        for label,pos in [('first',0),('final',-1)]:
            attempts=[r['attempts'][pos] for r in items]
            stats[label]={k:sum(bool(a.get('measured')) and bool(a.get(k)) for a in attempts)
                          for k in ('functional','security','joint')}
            stats[label]['measured']=sum(bool(a.get('measured')) for a in attempts)
            stats[label]['joint_rate_completed']=stats[label]['joint']/len(items) if items else None
        for r in items:
            stats['technical_errors'] += bool(technical_errors(r))
            stats['rows_with_adoption'] += any(a.get('generation',{}).get('cards') for a in r['attempts'])
            for a in r['attempts']:
                stats['selected_card_occurrences'] += len(a.get('generation',{}).get('retrieved_cards') or [])
                stats['adopted_card_occurrences'] += len(a.get('generation',{}).get('cards') or [])
        result['arms'][arm]=stats
    paired=[]
    for rep in (1,2):
        byarm={arm:{r['task_id']:r for r in rows if r['repeat']==rep and r['migration_arm']==arm}
               for arm in ('E0','E1')}
        common=byarm['E0'].keys() & byarm['E1'].keys()
        for tid in sorted(common):
            a,b=[byarm[arm][tid]['attempts'][-1] for arm in ('E0','E1')]
            paired.append({'task_id':tid,'repeat':rep,'E0_joint':bool(a.get('joint')),
                'E1_joint':bool(b.get('joint')),'both_measured':bool(a.get('measured') and b.get('measured')),
                'delta':int(bool(b.get('joint')))-int(bool(a.get('joint')))})
    result['paired']=paired
    result['net_joint_by_repeat']={str(rep):sum(p['delta'] for p in paired if p['repeat']==rep) for rep in (1,2)}
    usage=Counter();models=Counter();known=0;physical=0;settings_ok=True
    for path in (path for base in parts for path in (base/'wire').glob('*.request.json')):
        physical+=1;body=read(path)['body'];model=body.get('model');models[model]+=1
        if model==MODEL:
            settings_ok &= (body.get('temperature')==0 and body.get('thinking')=={'type':'disabled'}
                and body.get('max_tokens') in (256,4096)
                and [m['role'] for m in body.get('messages',[])]==['user'])
        raw=path.with_name(path.name.replace('.request.json','.response.raw'))
        u=None
        if raw.exists():
            payload=raw.read_bytes()
            if model=='text-embedding-3-large':
                try:u=json.loads(payload).get('usage')
                except ValueError:pass
            else:
                for line in payload.splitlines():
                    if line.startswith(b'data:'):
                        try:item=json.loads(line[5:].strip())
                        except ValueError:continue
                        if isinstance(item.get('usage'),dict):u=item['usage']
        if isinstance(u,dict):
            known+=1
            for k in ('prompt_tokens','completion_tokens','total_tokens'):
                usage[k]+=int(u.get(k) or 0)
    result['cost']={'physical_HTTP':physical,'HTTP_with_usage':known,'unknown_usage_HTTP':physical-known,
                    'known_usage':dict(usage),'request_models':dict(models),'currency_cost':None,
                    'settings_ok':settings_ok,'initial_analysis_included':True}
    write_json(run/'summary.json',result)
    return result


def worker(run, replay=False):
    """只调用封存run_one(P7)；每格独立请求日志，未知请求保留并停止，不自动重发。"""
    from methods.cle_ablation import runner
    from methods.cle_ablation.run_joint_contract import RequestBudget
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.context_pipeline import analysis_prompt
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.english_policy import assert_english_text
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    from methods.sct_trajectory.wire_recording import WireRecording
    from configs.cle_model_baseline_20261024.execute import record_validations
    p=read(run/'protocol.json'); cells=read(run/'schedule.json')
    assert p['model']==MODEL and p['Q_enabled'] is False
    memory_path=run/'inputs/memory.jsonl'; before=runner.digest(memory_path)
    nodes=runner.load_memory(memory_path)
    assert len(nodes)==1939 and all(runner.arm_spec('P7').__dict__[k]==v for k,v in
        {'memory':'full','reanalyze':True,'attempts':2,'negative':True}.items())
    tasks={str(t['index']):t for t in read(run/'inputs/tasks.json')}
    budget=RequestBudget(p['max_http'],p['max_conservative_tokens'],p['max_embedding_http'])
    stop=threading.Event(); semaphore=threading.Semaphore(4); output_lock=threading.Lock()
    budget_output_lock=threading.Lock()
    state={'status':'replaying' if replay else 'running','pid':os.getpid(),'time':now()}
    if not replay:write_json(run/'state.json',state);record_validations(run,'PLT')
    settings={'model':MODEL,'max_tokens':4096,'thinking':'disabled','temperature':0,'roles':['user'],'stream':True}
    if replay:
        def deny(*a,**k):raise ReplayStop('replay_network_or_credentials_disabled')
        native.load_key=deny
    else:
        import importlib.util
        spec=importlib.util.spec_from_file_location('migration_native_credentials',
            Path(p['original_project_root'])/'methods/sct_lifecycle_replay/chatanywhere_smoke.py')
        creds=importlib.util.module_from_spec(spec);spec.loader.exec_module(creds)
        native.load_key=creds.load_key

    def request_for(identity):
        journal=RequestJournal(run/'journals'/identity/'requests',mode='replay' if replay else 'live')
        native_client=lambda:native._requester(MODEL,180,4096,4,thinking='disabled',stream=True,
            endpoint='https://api.chatanywhere.org/v1/chat/completions',hard_timeout=300,
            gate_wait_timeout=600,semaphore=semaphore)
        call=journal.wrap(native_client,settings)
        def request(prompt):
            if stop.is_set():raise ReplayStop('stage_stopped_at_request_boundary')
            response=call(prompt)
            if response.get('model')!=MODEL:
                stop.set();raise ReplayStop('reported_model_mismatch')
            return response
        return request

    # 记录embedding原始返回向量；缓存只复用相同正文，未命中时才能进入真实请求。
    original_embed=EmbeddingClient._request
    embed_journal=RequestJournal(run/'journals/embedding/requests',mode='replay' if replay else 'live')
    def embed(client,texts):
        def live(_):
            before_usage=client.usage
            vectors=original_embed(client,texts);after=client.usage
            missing=after['usage_missing_calls']>before_usage['usage_missing_calls']
            return {'vectors':vectors,'usage':None if missing else
                {k:after[k]-before_usage[k] for k in ('prompt_tokens','total_tokens')}}
        return embed_journal.wrap(lambda:live,{'model':client.model,'operation':'embedding'})(
            json.dumps(texts,ensure_ascii=False))['vectors']
    EmbeddingClient._request=embed
    if replay and (run/'embedding_seed.sqlite3').exists():
        if (run/'replay_embeddings.sqlite3').exists():raise ReplayStop('replay_output_exists')
        shutil.copy2(run/'embedding_seed.sqlite3',run/'replay_embeddings.sqlite3')
    embedding=EmbeddingClient(cache_path=run/('replay_embeddings.sqlite3' if replay else 'embeddings.sqlite3'),
        key_loader=native.load_key,semaphore=semaphore,timeout=180,hard_timeout=300)

    def pair(cell):
        tid=cell['task_id'];pair_id=cell['pair_id'];task=tasks[tid]
        request=request_for('shared_'+pair_id)
        response=request(analysis_prompt(runner.plt_contract(task)))
        initial=_extract_json(_content(response))
        assert isinstance(initial,dict) and all(isinstance(initial.get(k),list) and initial[k]
            for k in ('vulnerability_hypothesis','functional_invariants'))
        assert_english_text(json.dumps(initial,ensure_ascii=False),context='initial_analysis')
        if not replay:write_json(run/'shared_starts'/f'{pair_id}.json',{'task_id':tid,
            'repeat':cell['repeat'],'initial_analysis':initial,'model':MODEL})
        for arm in cell['arms']:
            identity=pair_id+'_'+arm
            row=runner.run_one('PLT',task,'P7',request_for(identity),{'full':nodes},embedding,
                initial_analysis=copy.deepcopy(initial),max_experiences=3,retrieval_mode='semantic_llm',
                candidate_order=None,delta=None,retrieval_provider=empty_provider if arm=='E0' else None)
            row.update(migration_arm=arm,repeat=cell['repeat'],family_id=cell['family_id'],
                cell_id=identity,protocol=VERSION,Q_updates=0)
            target=run/('replay_rows' if replay else 'task_rows')/f'{identity}.json'
            write_json(target,row)
            if replay:
                if row!=read(run/'task_rows'/f'{identity}.json'):
                    raise ReplayStop('replay_row_mismatch:'+identity)
            else:
                for i,a in enumerate(row['attempts']):write_json(run/'attempts'/identity/f'{i}.json',a)
                with output_lock:
                    with (run/'rows.jsonl').open('a',encoding='utf-8') as f:
                        f.write(json.dumps(row,ensure_ascii=False)+'\n')
                    s=summarize(run)
                    state.update(completed_P7=s['completed_P7'],last_cell=identity,time=now())
                    write_json(run/'state.json',state)
                    print(json.dumps({'completed_P7':s['completed_P7'],'cell':identity,
                         'joint':row['attempts'][-1].get('joint'),'errors':technical_errors(row)},ensure_ascii=False),flush=True)
            errors=technical_errors(row)
            if errors:stop.set();raise ReplayStop('technical_gate_failed:'+identity+':'+','.join(errors))

    direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def transport(req,*args,**kwargs):
        if stop.is_set():raise ReplayStop('no_new_HTTP_after_failure')
        ensure_model_call_allowed(MODEL)
        body=json.loads(req.data)
        kind='embedding' if body['model']=='text-embedding-3-large' else 'chat'
        record=budget.reserve(kind,req.data.decode('utf-8'),attempts=1,
                              completion_cap=0 if kind=='embedding' else body['max_tokens'])
        # 多个HTTP线程共享同一.tmp；本批出现PermissionError，消除该确定的并发写入隐患。
        with budget_output_lock:
            write_json(run/'budget.json',budget.snapshot())
        response=direct.open(req,*args,**kwargs)
        record['status']='HTTP_opened'
        return response
    def batch(items):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(pair,c) for c in items]
            failure=None
            for f in as_completed(futures):
                try:f.result()
                except BaseException as exc:
                    stop.set();failure=failure or exc
                    for pending in futures:pending.cancel()
            if failure:raise failure
    try:
        if replay:
            urllib.request.urlopen=deny
            for c in cells:pair(c)
            write_json(run/'replay_summary.json',{'status':'passed','rows':48,'API_calls':0,'credentials_reads':0})
        else:
            with WireRecording(run/'wire',transport=transport):
                batch([c for c in cells if c['group']=='technical'])
                s=summarize(run)
                assert s['completed_P7']==8 and s['cost']['settings_ok']
                write_json(run/'technical_gate.json',{'status':'passed','completed_P7':8,
                    'accuracy_is_not_a_gate':True,'time':now()})
                batch([c for c in cells if c['group']=='development'])
            state.update(status='completed',pid=None)
    except BaseException as exc:
        state.update(status='stopped_technical',pid=None,error_type=type(exc).__name__,
                     reason=str(exc),time=now())
        raise
    finally:
        if not replay:
            state['memory_unchanged']=runner.digest(memory_path)==before
            write_json(run/'state.json',state);write_json(run/'budget.json',budget.snapshot());summarize(run)


def launch(run):
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    state=read(run/'state.json')
    if state['status']!='ready':raise RuntimeError('not_ready_no_automatic_resubmit')
    ensure_model_call_allowed(MODEL)
    lock=run/'launch.lock'
    with lock.open('x') as f:f.write(now())
    write_json(run/'state.json',{'status':'starting','pid':None,'time':now()})
    cmd=[sys.executable,'-B','-X','utf8',str(run/'source_bundle/configs/cle_v41_migration_20261025/run.py'),
         'worker','--run-root',str(run)]
    with (run/'stdout.log').open('ab') as out,(run/'stderr.log').open('ab') as err:
        proc=subprocess.Popen(cmd,cwd=run/'source_bundle',stdout=out,stderr=err,
             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    write_json(run/'launch.json',{'pid':proc.pid,'command':cmd,'time':now()})
    lock.unlink()
    print(json.dumps({'started':proc.pid,'run':str(run)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','launch','worker','report','replay'])
    parser.add_argument('--run-root',type=Path,default=RUN)
    a=parser.parse_args();run=a.run_root.resolve()
    if a.action=='prepare':prepare(run)
    elif a.action=='launch':launch(run)
    elif a.action=='worker':worker(run)
    elif a.action=='replay':worker(run,replay=True)
    else:print(json.dumps(summarize(run),ensure_ascii=False))


if __name__=='__main__':main()
