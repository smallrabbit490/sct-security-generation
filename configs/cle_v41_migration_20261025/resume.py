"""S1 v2恢复：原P7降级照常计分，按精确已付费前缀续接，不重跑交付行。"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'translation_work/diagnostics/20261025/cle_v41_migration_S1'
MODEL='deepseek-v4.1-flash-1017'
VERSION='cle-v41-native-P7-empty-vs-legacy1939-v2'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    # 物理预算和请求记录共用原子落盘修复；不改变预算算法或HTTP重试。
    from methods.sct_trajectory.replay_journal import write_json
    write_json(path,value)


def usage_from_bytes(payload,model):
    """只接受服务商实际报告的用量；缺失保持未知。"""
    if model=='text-embedding-3-large':
        try:return json.loads(payload).get('usage')
        except (ValueError,UnicodeDecodeError):return None
    usage=None
    for line in payload.splitlines():
        if not line.startswith(b'data:'):continue
        try:item=json.loads(line[5:].strip())
        except (ValueError,UnicodeDecodeError):continue
        if isinstance(item.get('usage'),dict):usage=item['usage']
    return usage


class RecoveryBudget:
    """同800万上限：已知按usage结算；在途及未知按UTF-8字节加输出上界占额。"""
    def __init__(self,path,prior_wires,*,max_tokens=8_000_000,max_calls=2000,max_embedding=200):
        self.path=path;self.lock=threading.RLock();self.entries=[]
        self.max_tokens=max_tokens;self.max_calls=max_calls;self.max_embedding=max_embedding
        for folder in prior_wires:
            for p in sorted(folder.glob('*.request.json')):
                body=read(p)['body'];entry=self.make_entry(body)
                raw=p.with_name(p.name.replace('.request.json','.response.raw'))
                usage=usage_from_bytes(raw.read_bytes(),body['model']) if raw.exists() else None
                if self.valid_usage(usage):entry.update(usage=usage,status='reported')
                else:entry['status']='historical_unknown'
                entry['source']=str(p);self.entries.append(entry)

    @staticmethod
    def valid_usage(u):return isinstance(u,dict) and type(u.get('total_tokens')) is int and u['total_tokens']>=0

    @staticmethod
    def make_entry(body):
        return {'model':body['model'],'bound':len(json.dumps(body,ensure_ascii=False).encode())+1024+
                (0 if body['model']=='text-embedding-3-large' else body['max_tokens']),
                'status':'reserved','usage':None}

    def charged(self):
        return sum(e['usage']['total_tokens'] if self.valid_usage(e['usage']) else e['bound'] for e in self.entries)

    def snapshot(self):
        return {'cap_tokens':self.max_tokens,'cap_HTTP':self.max_calls,'cap_embedding_HTTP':self.max_embedding,
            'charged_tokens_including_unknown_and_inflight_bounds':self.charged(),
            'known_reported_tokens':sum(e['usage']['total_tokens'] for e in self.entries if self.valid_usage(e['usage'])),
            'transport_attempts_including_prior':len(self.entries),'entries':copy.deepcopy(self.entries)}

    def reserve(self,body):
        with self.lock:
            entry=self.make_entry(body)
            embed=sum(e['model']=='text-embedding-3-large' for e in self.entries)
            if (len(self.entries)>=self.max_calls or self.charged()+entry['bound']>self.max_tokens
                or (body['model']=='text-embedding-3-large' and embed>=self.max_embedding)):
                raise RuntimeError('migration_budget_exhausted')
            self.entries.append(entry);write(self.path,self.snapshot())
            return entry

    def settle(self,entry,payload):
        with self.lock:
            u=usage_from_bytes(payload,entry['model'])
            entry.update(status='reported' if self.valid_usage(u) else 'unknown_after_close',usage=u)
            write(self.path,self.snapshot())


class AccountedResponse:
    """给原WireRecording透明保存响应字节，并在关闭时结算预留；不改返回正文。"""
    def __init__(self,response,budget,entry):
        self.response=response;self.budget=budget;self.entry=entry;self.chunks=[]
    def __getattr__(self,name):return getattr(self.response,name)
    def __iter__(self):return self
    def __next__(self):
        chunk=next(self.response);self.chunks.append(chunk);return chunk
    def read(self,*args):
        chunk=self.response.read(*args);self.chunks.append(chunk);return chunk
    def close(self):
        self.response.close();self.budget.settle(self.entry,b''.join(self.chunks))


def make_prefix_journal(cls,output,prior_folders):
    """每个cell独立精确匹配提示及序号，消费完旧前缀前禁止任何新付费请求。"""
    journal=cls(output,mode='resume')
    for folder in prior_folders:
        for path in sorted(folder.glob('*.json')):
            d=read(path)
            if d['status']!='completed':raise RuntimeError('unresolved_prior_request:'+str(path))
            if d['identity'] in journal.records:raise RuntimeError('duplicate_completed_request_identity')
            journal.records[d['identity']]=d;journal.prior.add(d['identity'])
    return journal


def prepare(run):
    """零API核对并封存v2；原15行、335失败和所有原日志只读。"""
    if read(run/'state.json')['status']!='stopped_technical':raise RuntimeError('unexpected_old_state')
    if (run/'recovery_segments.json').exists():raise RuntimeError('recovery_already_prepared')
    manifest=read(run/'source_manifest.json')
    assert all(digest(run/'source_bundle'/p)==v for p,v in manifest.items())
    inputs=read(run/'input_manifest.json')
    assert digest(run/'inputs/memory.jsonl')==inputs['memory']==digest(inputs['legacy_source'])
    assert read(run/'replay_results/completed_15/summary.json')['status']=='passed'
    saved={p.stem for p in (run/'task_rows').glob('*.json')}
    assert len(saved)==15 and '335_r1_E0' in saved
    journal_files=list((run/'journals').glob('*/requests/*.json'))
    assert all(read(p)['status']=='completed' for p in journal_files)
    schedule=read(run/'schedule.json')
    remaining=[{**c,'arms':[a for a in c['arms'] if c['pair_id']+'_'+a not in saved]}
               for c in schedule if any(c['pair_id']+'_'+a not in saved for a in c['arms'])]
    assert sum(len(c['arms']) for c in remaining)==33
    segment=run/'recovery_20261025_001';segment.mkdir(exist_ok=False)
    p=read(run/'protocol.json')
    p.update(protocol=VERSION,parent_protocol=p['protocol'],recovery_authorization='User 2026-10-25: update then continue experiment',
        stopping_policy='model JSON/selector/generation degradation retains native fallback and score; infrastructure/unknown requests/model mismatch/budget stop',
        budget_accounting='same8M cap; reported usage settles reservations; unknown/inflight retain conservative bounds; historical5 unknown retained',
        remaining_P7=33,reused_completed_P7=15,parser_modified=False,prompts_modified=False)
    write(segment/'protocol.json',p);write(segment/'schedule.json',remaining)
    write(segment/'prior_state.json',read(run/'state.json'))
    old_report=ROOT/'docs/CLE_v41Flash1017_P7空卡与1939卡迁移实验报告_20261025.md'
    shutil.copy2(old_report,segment/'prior_report_v1.md')
    write(segment/'checkpoint.json',{'completed_rows':{n:digest(run/'task_rows'/(n+'.json')) for n in sorted(saved)},
        'prior_journals':{str(f.relative_to(run)):digest(f) for f in journal_files},
        'input_manifest':inputs,'source_manifest':manifest})
    for name in ('report.py','run.py'):
        source=ROOT/'configs/cle_v41_migration_20261025'/name
        shutil.copy2(source,segment/('current_'+name))
    shutil.copy2(Path(__file__),segment/'resume.py')
    write(segment/'state.json',{'status':'ready','pid':None,'time':now()})
    write(run/'recovery_segments.json',[str(segment)])
    print(json.dumps({'prepared':str(segment),'remaining_P7':33,'API_calls':0}))


def worker(run,segment):
    # 只从首次运行封存源码导入P7、提示词、检索及验证器，恢复设施是独立新文件。
    bundle=run/'source_bundle';sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'src'))
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.replay_journal import RequestJournal,ReplayStop
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.context_pipeline import analysis_prompt
    from methods.sct_trajectory.agent_pipeline import _content,_extract_json
    from methods.sct_trajectory.english_policy import assert_english_text
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    from methods.sct_trajectory.wire_recording import WireRecording
    from configs.cle_model_baseline_20261024.execute import record_validations
    from configs.cle_v41_migration_20261025.run import empty_provider,technical_errors
    checkpoint=read(segment/'checkpoint.json');p=read(segment/'protocol.json')
    assert all(digest(run/'task_rows'/(n+'.json'))==h for n,h in checkpoint['completed_rows'].items())
    assert all(digest(run/f)==h for f,h in checkpoint['prior_journals'].items())
    assert all(digest(bundle/f)==h for f,h in checkpoint['source_manifest'].items())
    memory=run/'inputs/memory.jsonl';assert digest(memory)==checkpoint['input_manifest']['memory']
    nodes=runner.load_memory(memory);assert len(nodes)==1939
    tasks={str(t['index']):t for t in read(run/'inputs/tasks.json')}
    stop=threading.Event();slots=threading.Semaphore(4);output_lock=threading.Lock()
    budget=RecoveryBudget(segment/'budget.json',[run/'wire'],max_tokens=p['max_conservative_tokens'],
        max_calls=p['max_http'],max_embedding=p['max_embedding_http'])
    spec=importlib.util.spec_from_file_location('migration_recovery_credentials',
        Path(p['original_project_root'])/'methods/sct_lifecycle_replay/chatanywhere_smoke.py')
    creds=importlib.util.module_from_spec(spec);spec.loader.exec_module(creds);native.load_key=creds.load_key
    settings={'model':MODEL,'max_tokens':4096,'thinking':'disabled','temperature':0,'roles':['user'],'stream':True}
    reused=[]
    def journal(identity):
        j=make_prefix_journal(RequestJournal,segment/'journals'/identity/'requests',
                              [run/'journals'/identity/'requests'])
        return j
    def request_for(identity):
        j=journal(identity)
        call=j.wrap(lambda:native._requester(MODEL,180,4096,4,thinking='disabled',stream=True,
            endpoint='https://api.chatanywhere.org/v1/chat/completions',hard_timeout=300,gate_wait_timeout=600,
            semaphore=slots),settings)
        def request(prompt):
            if stop.is_set():raise ReplayStop('stopped_at_request_boundary')
            before=set(j.consumed);response=call(prompt)
            if response.get('model')!=MODEL:stop.set();raise ReplayStop('reported_model_mismatch')
            with output_lock:
                reused.extend({'cell':identity,'request':key} for key in j.consumed-before)
                write(segment/'reused_requests.json',reused)
            return response
        return request
    # 使用原运行已保存真实向量的独立副本，不修改原向量数据库。
    with sqlite3.connect(f'file:{(run/"embeddings.sqlite3").as_posix()}?mode=ro',uri=True) as src:
        with sqlite3.connect(segment/'embeddings.sqlite3') as dst:src.backup(dst)
    original_embed=EmbeddingClient._request
    def embed(client,texts):
        def live(_):
            before=client.usage;vectors=original_embed(client,texts);after=client.usage
            return {'vectors':vectors,'usage':None if after['usage_missing_calls']>before['usage_missing_calls'] else
                {k:after[k]-before[k] for k in ('prompt_tokens','total_tokens')}}
        # 原库中的请求均已沉入复制的真实向量缓存；这里只记录新未缓存文本。
        return embedding_new.wrap(lambda:live,{'model':client.model,'operation':'embedding'})(json.dumps(texts,ensure_ascii=False))['vectors']
    embedding_new=RequestJournal(segment/'journals/embedding_new/requests',mode='live')
    EmbeddingClient._request=embed
    embedding=EmbeddingClient(cache_path=segment/'embeddings.sqlite3',key_loader=native.load_key,
                              semaphore=slots,timeout=180,hard_timeout=300)
    record_validations(segment,'PLT')
    state={'status':'running','pid':os.getpid(),'completed_new_P7':0,'combined_completed_P7':15,'time':now()}
    write(segment/'state.json',state)
    def pair(cell):
        tid=cell['task_id'];pair_id=cell['pair_id'];task=tasks[tid]
        response=request_for('shared_'+pair_id)(analysis_prompt(runner.plt_contract(task)))
        try:
            initial=_extract_json(_content(response))
            if not isinstance(initial,dict) or not all(isinstance(initial.get(k),list) and initial[k]
                for k in ('vulnerability_hypothesis','functional_invariants')):raise ValueError('analysis_incomplete')
            assert_english_text(json.dumps(initial,ensure_ascii=False),context='initial_analysis')
            shared_error=None
        except Exception as exc:
            initial={'unmeasured':True};shared_error=type(exc).__name__
        write(segment/'shared_starts'/f'{pair_id}.json',{'initial_analysis':initial,'error':shared_error,'task_id':tid})
        for arm in cell['arms']:
            identity=pair_id+'_'+arm
            row=runner.run_one('PLT',task,'P7',request_for(identity),{'full':nodes},embedding,
                initial_analysis=copy.deepcopy(initial),max_experiences=3,retrieval_mode='semantic_llm',
                candidate_order=None,delta=None,retrieval_provider=empty_provider if arm=='E0' else None)
            row.update(migration_arm=arm,repeat=cell['repeat'],family_id=cell['family_id'],
                       cell_id=identity,protocol=VERSION,Q_updates=0)
            write(segment/'task_rows'/f'{identity}.json',row)
            for i,a in enumerate(row['attempts']):write(segment/'attempts'/identity/f'{i}.json',a)
            with output_lock:
                with (segment/'rows.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                state['completed_new_P7']+=1;state.update(combined_completed_P7=15+state['completed_new_P7'],
                    last_cell=identity,time=now());write(segment/'state.json',state)
                print(json.dumps({'completed':state['combined_completed_P7'],'cell':identity,
                    'joint':row['attempts'][-1].get('joint'),'native_degradations':technical_errors(row)},ensure_ascii=False),flush=True)
            # v2：仅模型结构化输出/采用/代码失败由原P7处理，不因此终止整批。
    direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def transport(req,*args,**kwargs):
        if stop.is_set():raise ReplayStop('no_new_HTTP_after_stop')
        ensure_model_call_allowed(MODEL)
        try:entry=budget.reserve(json.loads(req.data))
        except Exception:stop.set();raise ReplayStop('budget_exhausted_no_HTTP_dispatched') from None
        return AccountedResponse(direct.open(req,*args,**kwargs),budget,entry)
    try:
        with WireRecording(segment/'wire',transport=transport):
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures=[pool.submit(pair,c) for c in read(segment/'schedule.json')];failure=None
                for f in as_completed(futures):
                    try:f.result()
                    except BaseException as exc:
                        stop.set();failure=failure or exc
                        for pending in futures:pending.cancel()
                if failure:raise failure
        assert state['completed_new_P7']==33
        state.update(status='completed',pid=None,time=now())
    except BaseException as exc:
        state.update(status='stopped_infrastructure',pid=None,time=now(),reason=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        state['memory_unchanged']=digest(memory)==checkpoint['input_manifest']['memory']
        write(segment/'state.json',state)
        with budget.lock:write(segment/'budget.json',budget.snapshot())


def launch(run):
    sys.path.insert(0,str(ROOT))
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(MODEL)
    segment=Path(read(run/'recovery_segments.json')[-1])
    if read(segment/'state.json')['status']!='ready':raise RuntimeError('not_ready_no_resubmit')
    with (segment/'launch.lock').open('x') as f:f.write(now())
    write(segment/'state.json',{'status':'starting','pid':None,'time':now()})
    cmd=[sys.executable,'-B','-X','utf8',str(segment/'resume.py'),'worker','--run-root',str(run),'--segment',str(segment)]
    with (segment/'stdout.log').open('ab') as out,(segment/'stderr.log').open('ab') as err:
        proc=subprocess.Popen(cmd,cwd=run/'source_bundle',stdout=out,stderr=err,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    write(segment/'launch.json',{'pid':proc.pid,'command':cmd,'time':now()});(segment/'launch.lock').unlink()
    print(json.dumps({'started':proc.pid,'segment':str(segment)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','launch','worker'])
    parser.add_argument('--run-root',type=Path,default=RUN);parser.add_argument('--segment',type=Path)
    args=parser.parse_args();run=args.run_root.resolve()
    if args.action=='prepare':prepare(run)
    elif args.action=='launch':launch(run)
    else:worker(run,args.segment.resolve())


if __name__=='__main__':main()
