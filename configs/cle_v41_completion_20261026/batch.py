"""已授权v4.1迁移基础矩阵；原P7/原验证器，收益门只解释结果，不阻断包。"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import threading
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from configs.cle_v41_relation_20261026 import wiring
from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_v41_relation_20261026.live import AUTHORITY
from configs.cle_v41_completion_20261026.materials import Materials
from methods.cle_ablation import runner
from methods.sct_trajectory.agent_pipeline import _content, _extract_json
from methods.sct_trajectory.context_pipeline import analysis_prompt, JSON_FORMAT_POLICY
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / 'configs/cle_v41_completion_20261026'
RUN = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion'
RAW = ROOT / 'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def tasks_for(stage):
    kind = stage['kind']
    if kind in ('views','granularity'):
        tasks = read(RAW / 'v2/tasks_train.json')
        return tasks[:12] if kind == 'views' else tasks + read(RAW / 'v2/tasks_development.json')
    if kind in ('q_compare','q_selection'):
        return read(RAW / 'tasks_q_confirmation.json') if kind == 'q_compare' else fast_tasks()[:8]
    if kind == 'granularity_confirmation':
        return read(RAW / 'v2/tasks_granularity_confirmation.json')
    if kind == 'validation':
        ids = {x['task_id'] for x in read(ROOT/'configs/cle_v41_migration_20261025/protocol.json')['splits']['validation']}
        return [t for t in all_fast_tasks() if str(t['index']) in ids]
    if kind == 'counterfactual':
        return read(RAW/'v2/tasks_train.json')[:6]
    return fast_tasks() if kind in ('m1','profiles') else all_fast_tasks()


def all_fast_tasks():
    return read(ROOT/'translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48_restored_urls_v2.json')


def fast_tasks():
    p = read(ROOT/'configs/cle_v41_migration_20261025/protocol.json')
    by_id = {str(t['index']): t for t in all_fast_tasks()}
    return [by_id[t['task_id']] for t in p['splits']['development']]


def conditions(kind):
    return {'views':['B0','BF','BS','BFS','BM'], 'granularity':['L0','L1','L2','L3','L4'],
            'profiles':['P00','P13','P22'], 'contract':['P7','PUBLIC'],
            'q_compare':['Q0','Q1','Q2','Q3'], 'q_selection':['Q0','Q1','Q2','Q3'],
            'm1':['protect_none','protect_m1'], 'granularity_confirmation':['fixed','rule','classifier'],
            'validation':['CONTROL','SELECTED'], 'counterfactual':['empty_edit','memory_edit']}[kind]


def make_schedule(stage, tasks):
    if stage['kind']=='granularity':
        from methods.cle_ablation.granularity_results import make_schedule as original_schedule
        return [{**cell,'condition':cell['memory_level']} for cell in original_schedule(read(RAW/'manifest.json'),20261023)]
    rng, result = random.Random(20261026), []
    repetitions = 5 if stage['kind'] == 'q_selection' else 2
    for repeat in range(1,repetitions+1):
        for task in tasks:
            arms = conditions(stage['kind'])[:]
            rng.shuffle(arms)
            for arm in arms:
                result.append({'task_id':str(task['index']), 'family_id':task['family_id'], 'repeat':repeat,
                               'condition':arm,'cell_id':f"{task['index']}_r{repeat}_{arm}"})
    return result


def selector_pre_dispatch_failure(row):
    """只恢复本次已观测的共享向量等待故障；有效选卡及模型解析失败不重跑。"""
    trace = row.get('retrieval_trace') or {}
    return (row.get('stage_id') == 'D03a' and row.get('status') == 'selection_unmeasured'
            and trace.get('errors') == ['embedding_flight_wait_timeout']
            and not trace.get('candidate_ids') and not trace.get('selected_ids'))


class Batch:
    """每包独立费用和原生行；完成项复用，所有已规划格都执行而不按分数筛选。"""
    def __init__(self, stage, resume_sources=(), segment=None, offline_replay=False):
        control=RUN/'dispatch_control.json'
        if not offline_replay and control.exists() and not read(control)['paid_execution_enabled']:
            raise RuntimeError('paid_execution_paused_by_latest_user_instruction')
        from methods.sct_trajectory import run_closed_loop as native
        from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
        self.stage, self.tasks, self.kind = stage, tasks_for(stage), stage['kind']
        self.out = Path(segment) if segment else RUN / stage['id']
        self.prior = [Path(p) for p in resume_sources]
        self.offline_replay=offline_replay
        self.by_id = {str(t['index']):t for t in self.tasks}
        self.cells = make_schedule(stage,self.tasks)
        if offline_replay:
            completed={p.stem for root in self.prior for p in (root/'task_rows').glob('*.json')}
            self.cells=[cell for cell in self.cells if cell['cell_id'] in completed]
            if not self.cells:raise ValueError('no_completed_cells_to_replay')
        self.partial_replay=offline_replay and len(self.cells)!=stage['planned_runs']
        if not offline_replay and len(self.cells) != stage['planned_runs']:
            raise ValueError('stage_manifest_count_mismatch')
        self.slots = threading.Semaphore(4)
        self.context=threading.local()
        self.row_lock=threading.RLock()
        shared=RUN/'shared_inputs';shared.mkdir(parents=True,exist_ok=True)
        memory_source=ROOT/'translation_work/diagnostics/20261020/cle_q_online_v1/D_grow/frozen/m_star_q.jsonl'
        memory_snapshot=shared/'memory1939.jsonl'
        if not memory_snapshot.exists():shutil.copy2(memory_source,memory_snapshot)
        if self.kind=='m1':
            from .policies import ARCHIVE
            target=shared/'m1_source_bank.json'
            if not target.exists():shutil.copy2(ARCHIVE,target)
        self.nodes = runner.load_memory(memory_snapshot)
        self.excluded_source_cards = []
        self.source_families = {}
        selected_kind=read(RUN/'S4_selection.json')['chosen']['kind'] if self.kind=='validation' else self.kind
        if selected_kind in ('granularity','granularity_confirmation'):
            missing = set(read(RAW/'C01_source_availability_v1/summary.json')['L4_unavailable_cards'])
            self.excluded_source_cards = sorted(missing)
            self.nodes = [n for n in self.nodes if n.invariant_id not in missing]
            from configs.cle_memory_mechanisms_20261023.prepare_granularity_views import load_materials
            self.source_families = {key:value['source_family_id'] for key,value in load_materials()[2].items()}
        from methods.cle_ablation.run_memory_q import shuffled_memory
        self.shuffled = shuffled_memory(self.nodes,20261015,scope='cwe')
        p = {**read(CFG/'protocol.json'), 'protocol':'cle-v41-completion-'+stage['id']+'-v1',
            'planned_P7':len(self.cells),'stage':stage,'actual_memory_count':len(self.nodes),
            'Q_used':self.kind in ('q_compare','q_selection'), 'Q_updates':False,
            'memory_snapshot':str(memory_snapshot),'memory_original':str(memory_source),
            'excluded_in_all_granularity_levels':self.excluded_source_cards,
            'selector_character_limit':420000,'resume_sources':[str(p) for p in self.prior],
            'technical_recovery_policy':'reuse completed responses exactly; retain unknown charges; unfinished requests may be retried in a new segment under current completion authorization and cumulative package cap',
            'budget_proposed':{'conservative_model_and_embedding_tokens':stage['budget']['tokens'],
                'total_physical_HTTP_attempts':stage['budget']['HTTP'],
                'embedding_HTTP_attempts_included_in_total':stage['budget']['embedding_HTTP']}}
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def no_network(*args,**kwargs):raise AssertionError('zero_API_replay_forbids_physical_network')
        def factory(identity):
            if offline_replay:raise RuntimeError('offline_replay_missing_response_no_HTTP')
            return native._requester(wiring.SETTINGS['model'],180,4096,4,thinking='disabled',stream=True,
                endpoint='https://api.chatanywhere.org/v1/chat/completions', hard_timeout=300,
                gate_wait_timeout=600,semaphore=self.slots)
        p['paid_execution_enabled']=not offline_replay
        self.io = StudyExecution(self.out,p,self.cells,client_factory=factory,physical_open=no_network if offline_replay else direct.open,
            live=not offline_replay,fixed_eight=False,resume_sources=self.prior,protected_paths=[memory_source,memory_snapshot])
        if offline_replay:
            self.io.replay_source=self.out
            self.io.state['evidence_kind']='zero_API_saved_real_response_replay'
        self.io.save('launch',{'pid':os.getpid(),'authorization':AUTHORITY,'stage_id':stage['id'],
            'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'runner':'configs.cle_v41_completion_20261026.batch',
            'runtime_source':'source_bundle; includes current uncommitted implementation'})
        self.io.save('inputs/tasks',self.tasks)
        source = self.out/'source_bundle'
        for directory in ('methods','src','configs/cle_v41_completion_20261026','configs/cle_v41_relation_20261026','configs/cle_v41_migration_20261025'):
            for path in (ROOT/directory).rglob('*.py'):
                target = source/path.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        import methods.sct_trajectory.semantic_retrieval as semantic
        semantic.MAX_SELECTOR_CHARS=420000
        seed = self.prior[-1]/'embeddings.sqlite3' if self.prior else ROOT/'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/embeddings.sqlite3'
        cache = self.out/'embeddings.sqlite3'
        with sqlite3.connect(f'file:{seed.as_posix()}?mode=ro',uri=True) as src:
            with sqlite3.connect(cache) as dst:src.backup(dst)
        self.embedding = EmbeddingClient(cache_path=cache,key_loader=native.load_key,semaphore=self.slots,
            timeout=180,hard_timeout=300,gate_wait_timeout=600)
        original = self.embedding._request
        def embedded(texts):
            def call(items):
                before=self.embedding.usage; vectors=original(items);after=self.embedding.usage
                usage=None if after['usage_missing_calls']>before['usage_missing_calls'] else {
                    k:after[k]-before[k] for k in ('prompt_tokens','total_tokens')}
                return {'vectors':vectors,'usage':usage}
            return self.io.embedding(texts,call)['vectors']
        self.embedding._request=embedded
        self.materials = Materials(RUN/'shared_materials',self.io.request_for)
        material_lock=threading.RLock()
        for name in ('view_specs','level_materials'):
            function=getattr(self.materials,name)
            def locked(*args,_function=function,**kwargs):
                with material_lock:return _function(*args,**kwargs)
            setattr(self.materials,name,locked)
        self.starts, self.rows = {}, []
        self.replay_rows={}
        self.policy_rows={}
        self.profile_prefixes={}
        for prior in self.prior:
            for path in (prior/'task_rows').glob('*.json'):
                row=read(path)
                if offline_replay:self.replay_rows[row['cell_id']]=row
                if not offline_replay and self.kind == 'q_selection' and selector_pre_dispatch_failure(row):
                    self.io.reused_cell_ids.discard(row['cell_id'])
                    continue
                if not offline_replay and row['cell_id'] not in {r['cell_id'] for r in self.rows}:self.rows.append(row)
                if not offline_replay and row.get('selected_level'):
                    self.policy_rows[str(row['task_id']),row['repeat'],row['selected_level']]=row
        if not offline_replay and self.kind == 'q_selection':
            self.io.reused_cell_ids = {row['cell_id'] for row in self.rows}
        self.io.save('state',self.io.state)

    def retrieve(self, query, request, arm='Q0'):
        from methods.sct_trajectory.retriever import HskTreeRetriever
        from methods.sct_trajectory.hsk_tree import HskTree
        from methods.sct_trajectory.ablation import get_config
        order = None if arm=='Q0' else 'similarity' if arm=='Q1' else 'q'
        nodes=self.shuffled if arm=='Q3' else self.nodes
        if self.source_families:
            nodes=[n for n in nodes if self.source_families[n.invariant_id] != self.context.family]
        engine=HskTreeRetriever(HskTree(),requester=request,ablation=get_config('A7'),
            retrieval_mode='semantic_llm',embedding_client=self.embedding,semantic_delta=-1,
            lambda_q=.5,candidate_order=order)
        cards=engine.search(query,limit=3,pool_nodes=nodes)
        return cards,engine.last_hier_trace

    def public_replay_executor(self,cell_id):
        """重跑公开检查；仅随机临时路径可不同，反馈逐字复用已保存证据。"""
        from methods.sct_trajectory.internal_checks import execute_checks
        from methods.sct_trajectory.public_repair_policy import bind_public_result
        source=self.replay_rows[cell_id];position=0
        def normalize(value):
            if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
            if isinstance(value,list):return [normalize(v) for v in value]
            if isinstance(value,str):return re.sub(r'case_[A-Za-z0-9_]+(?=[/\\]worker\.py)', 'case_<temporary>',value)
            return value
        def execute(code,entry_point,suite,*,backend,timeout):
            nonlocal position
            attempt=source['attempts'][position];position+=1
            if code!=attempt['code'] or suite!=source['internal_suite']:
                raise ReplayStop('public_replay_code_or_suite_differed')
            actual=bind_public_result(code,suite,execute_checks(code,entry_point,suite,backend=backend,timeout=timeout))
            saved=attempt['internal_checks'];matched=normalize(actual)==normalize(saved)
            self.io.save(f'offline_public_checks/{cell_id}_{position-1}',
                {'actual':actual,'saved':saved,'semantic_match_ignoring_temporary_worker_path':matched,
                 'feedback_source':'exact saved public evidence; actual checks independently reexecuted'})
            if not matched:raise ReplayStop('public_replay_check_result_differed')
            return copy.deepcopy(saved)
        return execute

    def public_resume_executor(self,cell_id):
        """Retain the original public feedback before re-entering repair retrieval."""
        from methods.sct_trajectory.internal_checks import execute_checks
        from methods.sct_trajectory.public_repair_policy import bind_public_result
        saved_results=[];saved_feedback=[]
        for prior in self.prior:
            for path in sorted((prior/'public_checkpoints'/cell_id).glob('*.json')):
                saved_results.append(read(path)['result'])
            for path in sorted((prior/'journals'/cell_id/'requests').glob('*.json')):
                for line in read(path)['prompt'].splitlines():
                    if line.startswith('Permitted execution feedback: '):
                        evidence=json.JSONDecoder().raw_decode(line.split(': ',1)[1])[0]
                        if evidence.get('internal_checks',{}).get('public_binding'):
                            saved_results.append(evidence['internal_checks'])
                        elif evidence.get('internal_checks',{}).get('cases'):
                            saved_feedback.append(evidence['internal_checks'])
        position=0
        def normalize(value):
            if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
            if isinstance(value,list):return [normalize(v) for v in value]
            if isinstance(value,str):return re.sub(r'case_[A-Za-z0-9_]+(?=[/\\]+worker\.py)', 'case_<temporary>',value)
            return value
        def execute(code,entry_point,suite,*,backend,timeout):
            nonlocal position
            actual=bind_public_result(code,suite,execute_checks(code,entry_point,suite,backend=backend,timeout=timeout))
            matching=[item for item in saved_results if item['public_binding']==actual['public_binding']]
            from methods.sct_trajectory.public_repair_policy import public_repair_feedback
            visible=public_repair_feedback(suite,actual,{})['internal_checks']
            prior_feedback=next((item for item in saved_feedback if normalize(item)==normalize(visible)),None)
            if prior_feedback:
                result=copy.deepcopy(actual)
                errors={item['id']:item for item in prior_feedback['cases']}
                for item in result['cases']:
                    if 'error' in errors[item['id']]:item['error']=errors[item['id']]['error']
            elif matching:
                if normalize(matching[0])!=normalize(actual):raise ReplayStop('public_resume_check_result_differed')
                result=copy.deepcopy(matching[0])
            else:result=actual
            self.io.save(f'public_checkpoints/{cell_id}/{position}',{'result':result,'actual':actual,'saved_feedback_reused':result!=actual or bool(matching)})
            position+=1
            return result
        return execute

    def start(self, task, repeat, selected=True):
        key=f"{task['index']}_r{repeat}"
        if key not in self.starts:
            for prior in reversed(self.prior):
                path=prior/'shared_starts'/(key+'.json')
                if path.exists():
                    self.starts[key]=read(path)
                    return copy.deepcopy(self.starts[key])
            request=self.io.request_for('shared_initial_'+key)
            response=request(analysis_prompt(runner.plt_contract(task)))
            try:
                initial=_extract_json(_content(response))
                assert isinstance(initial,dict) and all(isinstance(initial.get(k),list) and initial[k]
                    for k in ('vulnerability_hypothesis','functional_invariants'))
                from methods.sct_trajectory.english_policy import assert_english_text
                assert_english_text(json.dumps(initial,ensure_ascii=False),context='initial_analysis')
            except (ValueError,AssertionError): initial={'unmeasured':True}
            query={**runner.plt_contract(task),'threat_analysis':initial,'current_code':'','failure_evidence':{}}
            cards,trace=self.retrieve(query,self.io.request_for('shared_selection_'+key)) if selected else ([],{})
            self.starts[key]={'public_contract':runner.plt_contract(task),'query':query,'initial_analysis':initial,
                'selected_cards':cards,'retrieval_trace':trace,'repeat':repeat}
            self.io.save('shared_starts/'+key,self.starts[key])
        return copy.deepcopy(self.starts[key])

    def one(self, cell):
        task=self.by_id[cell['task_id']]; arm=cell['condition'];request=self.io.request_for(cell['cell_id'])
        self.context.family=task['family_id']
        if self.kind=='q_selection':
            start=self.start(task,1,selected=False)
            try:cards,trace=self.retrieve(start['query'],request,arm)
            except RuntimeError as exc:
                if not hasattr(exc,'retrieval_trace'):raise
                return {'task_id':str(task['index']),'condition':arm,'selected_ids':None,
                    'status':'selection_unmeasured','retrieval_trace':exc.retrieval_trace,
                    'code_generated':False,'Q_updates':0,'error_type':type(exc).__name__}
            return {'task_id':str(task['index']),'condition':arm,'selected_ids':[c['invariant_id'] for c in cards],
                    'status':'initial_analysis_unmeasured' if start['initial_analysis'].get('unmeasured') else 'completed',
                    'retrieval_trace':trace,'code_generated':False,'Q_updates':0}
        if self.kind=='m1':
            from configs.cle_v41_completion_20261026.policies import run_m1
            return run_m1(task,arm,request)
        if self.kind=='counterfactual':
            from configs.cle_v41_completion_20261026.policies import run_counterfactual
            return run_counterfactual(task,cell,request)
        if self.kind=='validation':
            from configs.cle_v41_completion_20261026.policies import validation_cell
            return validation_cell(self,cell)
        start=self.start(task,cell['repeat'],selected=self.kind not in ('q_compare','contract'))
        if self.kind=='granularity_confirmation':
            from configs.cle_v41_completion_20261026.policies import predict_level
            from methods.cle_ablation.memory_granularity_study import run_one_level
            level=predict_level(task,arm,bool(start['selected_cards']))
            key=str(task['index']),cell['repeat'],level
            if key in self.policy_rows:
                source=self.policy_rows[key];row=copy.deepcopy(source)
                row.update(memory_policy=arm,reused_result_from_cell=source.get('reused_result_from_cell',source['cell_id']))
                return row
            row=run_one_level(task,start,level,request,lambda q:self.retrieve(q,request),self.materials.level_materials)
            row.update(memory_policy=arm,selected_level=level)
            # 同题×重复组串行，按原排程选择策略；相同档位无需再买一次同输入生成。
            row['cell_id']=cell['cell_id'];self.policy_rows[key]=copy.deepcopy(row)
            return row
        if self.kind=='granularity':
            from methods.cle_ablation.memory_granularity_study import run_one_level
            return run_one_level(task,start,arm,request,
                lambda q:self.retrieve(q,request),self.materials.level_materials)
        if self.kind=='views':
            from methods.cle_ablation.run_memory_view_probe import ViewProvider
            provider=ViewProvider(start,arm,lambda q:self.retrieve(q,request),self.materials.view_specs)
            return runner.run_one('PLT',task,'P7',request,{'full':[]},initial_analysis=start['initial_analysis'],
                                  retrieval_provider=provider,max_experiences=3)
        if self.kind=='profiles':
            from methods.cle_prompt_ablation.prompt_profiles import get_profile, render_generation_prompt
            original_request=request
            prefix_key=f"{task['index']}_r{cell['repeat']}"
            prefix=self.profile_prefixes.setdefault(prefix_key,{'responses':{},'generation_base':None})
            before_generation=True
            def request(prompt):
                nonlocal before_generation
                if str(prompt).startswith(wiring.GENERATION):
                    if before_generation:
                        base=str(prompt)
                        if prefix['generation_base'] not in (None,base):raise ReplayStop('profile_c0_generation_base_diverged')
                        prefix['generation_base']=base
                    before_generation=False
                    content=str(prompt).split('\nAdopted experiences: ',1)[1]
                    cards=json.JSONDecoder().raw_decode(content)[0]
                    return original_request(render_generation_prompt(str(prompt),cards,get_profile(arm)))
                if before_generation:
                    key=str(prompt)
                    if key not in prefix['responses']:
                        prefix['responses'][key]=self.io.request_for('shared_profile_prefix_'+prefix_key)(prompt)
                        self.io.save('shared_profile_prefixes/'+prefix_key,prefix)
                    return copy.deepcopy(prefix['responses'][key])
                return original_request(prompt)
            calls=0
            def provider(query):
                nonlocal calls
                calls+=1
                return (copy.deepcopy(start['selected_cards']),copy.deepcopy(start['retrieval_trace'])) if calls==1 else self.retrieve(query,request)
        elif self.kind=='contract':
            from methods.cle_ablation.joint_contract import run_one as public_run
            if arm=='PUBLIC':
                options={'check_executor':self.public_replay_executor(cell['cell_id']) if self.offline_replay else self.public_resume_executor(cell['cell_id'])}
                return public_run('PLT',task,request,lambda q:self.retrieve(q,request)[0],initial_analysis=start['initial_analysis'],**options)
            provider=lambda q:self.retrieve(q,request)
        elif self.kind=='q_compare':
            provider=lambda q:self.retrieve(q,request,arm)
        else:
            raise NotImplementedError('stage_adapter_pending:'+self.kind)
        return runner.run_one('PLT',task,'P7',request,{'full':[]},initial_analysis=start['initial_analysis'],
                              retrieval_provider=provider,max_experiences=3)

    def checkpoint(self):
        counts={}
        for arm in conditions(self.kind):
            items=[r for r in self.rows if r['condition']==arm]
            finals=[r.get('final', (r.get('attempts') or [{}])[-1]) for r in items]
            counts[arm]={'completed':len(items), 'measured':sum(bool(a.get('measured')) for a in finals),
                **{k:sum(bool(a.get('measured')) and bool(a.get(k)) for a in finals) for k in ('functional','security','joint')}}
        self.io.save('summary',{'stage':self.stage['id'],'planned':len(self.cells),'completed':len(self.rows),
            'status':self.io.state['status'],'arms':counts,'Q_updates':0,'cards_generated':0,
            'cost':self.io.budget.snapshot(),'source_partition_method':'AI source-only or explicitly flagged field-rule fallback'})
        with self.io.lock:journals=list(self.io.journals.items())
        self.io.save('logical_summary',{name:j.summary() for name,j in journals})
        (self.out/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in self.rows),encoding='utf-8')

    def run(self):
        try:
            with self.io.physical_records():
                if self.kind=='q_selection':
                    # 五重复共用同一首次查询；先各题准备一次，避免跨重复并发重复付费初析。
                    with ThreadPoolExecutor(max_workers=4) as preparation:
                        futures=[preparation.submit(self.start,task,1,False) for task in self.tasks]
                        for future in as_completed(futures):future.result()
                groups=defaultdict(list)
                done={r['cell_id'] for r in self.rows}
                for cell in self.cells:
                    if cell['cell_id'] not in done:groups[cell['task_id'],cell['repeat']].append(cell)
                def group(cells):
                    for cell in cells:
                        row=self.one(cell)
                        row.update(condition=cell['condition'],cell_id=cell['cell_id'],repeat=cell['repeat'],
                            family_id=cell['family_id'],stage_id=self.stage['id'],Q_updates=0)
                        if 'phase' in cell:row['phase']=cell['phase']
                        self.io.save('task_rows/'+cell['cell_id'],row)
                        with self.row_lock:
                            self.rows.append(row)
                            self.io.state.update(status='running',completed_P7=len(self.rows),actual_paid_P7=0 if self.offline_replay else sum(not r.get('reused_result_from_cell') for r in self.rows),
                                exact_same_policy_result_reused=sum(bool(r.get('reused_result_from_cell')) for r in self.rows),
                                reused_completed_P7=sum(r['cell_id'] in self.io.reused_cell_ids for r in self.rows),
                                new_completed_P7=sum(r['cell_id'] not in self.io.reused_cell_ids and not r.get('reused_result_from_cell') for r in self.rows))
                            self.io.save('state',self.io.state)
                            self.checkpoint()
                with ThreadPoolExecutor(max_workers=4) as workers:
                    futures=[workers.submit(group,cells) for cells in groups.values()]
                    for future in as_completed(futures):future.result()
            self.io.state.update(status='completed',completed_P7=len(self.rows))
            if self.offline_replay:
                from .policies import final
                original={r['cell_id']:r for prior in self.prior for path in (prior/'task_rows').glob('*.json') for r in [read(path)]}
                def signature(r):
                    return ([a.get('code') for a in r.get('attempts',[])],r.get('selected_ids'),
                            {k:final(r).get(k) for k in ('code','functional','security','joint','measured')})
                differences=[r['cell_id'] for r in self.rows if signature(r)!=signature(original[r['cell_id']])]
                self.io.state.update(status='replay_differences' if differences else 'replay_passed_partial' if self.partial_replay else 'replay_passed',
                    differences=differences,new_HTTP=0,live_manifest_planned=self.stage['planned_runs'])
        except BaseException as exc:
            self.io.state.update(status='needs_technical_recovery',reason=self.io.reason or str(exc),error_type=type(exc).__name__,error_detail=str(exc))
        finally:
            self.io.state.update(inputs_unchanged=self.io.input_state()==self.io.inputs_before)
            self.io.save('state',self.io.state);self.checkpoint()
        print(json.dumps(self.io.state,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage')
    parser.add_argument('--segment',type=Path)
    parser.add_argument('--resume-source',type=Path,action='append',default=[])
    parser.add_argument('--offline-replay',action='store_true')
    args=parser.parse_args()
    stage=next(s for s in read(CFG/'protocol.json')['stages'] if s['id']==args.stage)
    Batch(stage,args.resume_source,args.segment,args.offline_replay).run()


if __name__=='__main__':main()
