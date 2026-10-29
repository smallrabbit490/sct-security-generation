"""完整迁移的固定名单、预算和来源呈现检查；不创建真实请求客户端。"""
import json
import tempfile
import unittest
import copy
import threading
import time
import itertools
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from configs.cle_v41_completion_20261026 import batch
from configs.cle_v41_completion_20261026.materials import Materials
from methods.sct_trajectory.memory_views import source_projection, render_view
from configs.cle_v41_completion_20261026 import policies


class CompletionBatchTest(unittest.TestCase):
    def test_every_ready_matrix_matches_predeclared_count_and_unique_cells(self):
        p=batch.read(batch.CFG/'protocol.json')
        for stage in p['stages']:
            if stage['kind'] not in ('views','profiles','contract','granularity','q_selection','q_compare','granularity_confirmation','validation','m1','counterfactual'):
                continue
            with self.subTest(stage=stage['id']):
                tasks=batch.tasks_for(stage)
                cells=batch.make_schedule(stage,tasks)
                self.assertEqual(len(cells),stage['planned_runs'])
                self.assertEqual(len({c['cell_id'] for c in cells}),len(cells))
                self.assertEqual(len({t['family_id'] for t in tasks}),len(tasks))

    def test_granularity_train_development_and_confirmation_are_disjoint(self):
        stages=batch.read(batch.CFG/'protocol.json')['stages']
        train=batch.tasks_for(next(s for s in stages if s['id']=='C02'))
        confirmation=batch.tasks_for(next(s for s in stages if s['id']=='C04b'))
        self.assertEqual(len(train),48)
        self.assertEqual(len(confirmation),24)
        self.assertFalse({t['family_id'] for t in train}&{t['family_id'] for t in confirmation})

    def test_field_rule_fallback_keeps_exact_source_characters_and_is_flagged(self):
        parent=batch.ROOT/'translation_work/temp';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent,prefix='completion_material_') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(parent.resolve()))
            def request_for(identity):
                return lambda prompt:{'choices':[{'message':{'content':'invalid JSON'}}]}
            cards=[{'invariant_id':'fixture-card','kind':'hint','status':'active',
                    'high_level_invariant':'Reject untrusted code execution.',
                    'negative_guardrail':'Preserve valid inputs.', 'applicability':'Only if code is untrusted.'}]
            specs=Materials(folder,request_for).view_specs(cards)
            spec=specs['fixture-card']
            self.assertEqual(spec['annotation_method'],'rule_partition_after_AI_format_failure')
            rendered=render_view(source_projection(cards[0]),spec,'BFS')
            texts=[item['text'] for field in ('functional_preservation','security_action','applicability_and_source_context')
                   for item in rendered[field]]
            for field in ('high_level_invariant','negative_guardrail','applicability'):
                self.assertIn(cards[0][field],texts)

    def test_public_features_cannot_consume_answers_scores_or_identifiers(self):
        task={'task_description':{'function_name':'f','description':'Return input.',
              'arguments':'x: str','context':'Runtime TABLE is supplied.'},'index':1,'family_id':'first',
              'ground_truth':{'answer':'hidden'},'joint':True}
        other=copy.deepcopy(task);other.update(index=99,family_id='second',ground_truth={'answer':'changed'},joint=False)
        self.assertEqual(policies.features(task),policies.features(other))
        self.assertEqual(policies.rule_level(task,False),'L0')
        self.assertEqual(policies.rule_level(task,True),'L3')

    def test_small_logistic_is_fitted_without_external_dependency_or_private_fields(self):
        a={'description':'small input','arguments':'x'}
        b={'description':'write '*50,'arguments':'x y z','context':'Runtime CONFIG is supplied'}
        fit=policies.fit_logistic([policies.features(a)]*4+[policies.features(b)]*4,['L1']*4+['L3']*4)
        model={'type':'multinomial_logistic','fit':fit,'fixed':'L2'}
        self.assertEqual(policies.predict(a,model)[0],'L1')
        self.assertEqual(policies.predict(b,model)[0],'L3')

    def test_validation_uses_a_consumer_copy_not_a_shared_mutable_kind(self):
        fake=SimpleNamespace(kind='validation',one=lambda cell:{'cell':cell})
        chosen={'kind':'profiles','treated':'P13','control':'P00'}
        with patch.object(policies,'read',return_value={'chosen':chosen}):
            row=policies.validation_cell(fake,{'condition':'SELECTED','cell_id':'fixture'})
        self.assertEqual(fake.kind,'validation')
        self.assertEqual(row['cell']['condition'],'P13')

    def test_M1_repair_limit_preserves_incumbent_and_prevents_third_generation(self):
        from methods.a7_exploration import workflow
        initial={'code':'first','issues':['a','b'],'checks':{'cases':[]}}
        after={'code':'second','issues':['a'],'checks':{'cases':[]}}
        with patch.object(workflow,'generate',return_value=('second',{})) as generation,patch.object(workflow,'inspect',return_value=after):
            delivered,attempts,reason=workflow.repair_loop({}, {}, {}, None, initial,max_repairs=1)
        self.assertEqual(generation.call_count,1)
        self.assertEqual(delivered['code'],'second')
        self.assertEqual(len(attempts),2)
        self.assertEqual(reason,'predeclared_repair_limit')

    def test_four_group_execution_preserves_each_pair_order_and_count(self):
        parent=batch.ROOT/'translation_work/temp'
        with tempfile.TemporaryDirectory(dir=parent,prefix='completion_parallel_') as folder:
            study=batch.Batch.__new__(batch.Batch)
            study.stage={'id':'fixture'}
            study.out=Path(folder);study.kind='views';study.offline_replay=False
            study.cells=[{'task_id':str(t),'repeat':r,'condition':arm,'cell_id':f'{t}_{r}_{arm}','family_id':str(t)}
                         for t in (1,2) for r in (1,2) for arm in ('A','B')]
            study.rows=[];study.row_lock=threading.RLock();study.checkpoint=lambda:None
            study.io=SimpleNamespace(physical_records=nullcontext,state={},save=lambda *args:None,
                input_state=lambda:{},inputs_before={},reason=None,reused_cell_ids=set())
            lock=threading.Lock();active=peak=0;orders={}
            def one(cell):
                nonlocal active,peak
                with lock:
                    active+=1;peak=max(peak,active)
                    orders.setdefault((cell['task_id'],cell['repeat']),[]).append(cell['condition'])
                time.sleep(.005)
                with lock:active-=1
                return {'task_id':cell['task_id'],'attempts':[{'measured':True,'joint':False}]}
            study.one=one
            study.run()
            self.assertEqual(study.io.state['status'],'completed')
            self.assertEqual(len(study.rows),8)
            self.assertLessEqual(peak,4)
            self.assertGreater(peak,1)
            self.assertTrue(all(value==['A','B'] for value in orders.values()))

    def test_identical_granularity_policy_reuses_the_paid_result_without_a_request(self):
        study=batch.Batch.__new__(batch.Batch);study.kind='granularity_confirmation'
        study.context=threading.local();study.by_id={'1':{'index':1,'family_id':'family'}}
        requests=[]
        study.io=SimpleNamespace(request_for=lambda identity:lambda prompt:requests.append(prompt))
        study.start=lambda *args,**kwargs:{'selected_cards':[{'invariant_id':'a'}]}
        study.policy_rows={('1',1,'L2'):{'cell_id':'1_r1_fixed','task_id':'1','selected_level':'L2',
            'attempts':[{'code':'def f(): pass','measured':True,'joint':True}]}}
        with patch.object(policies,'predict_level',return_value='L2'):
            row=study.one({'task_id':'1','condition':'classifier','repeat':1,'cell_id':'1_r1_classifier'})
        self.assertEqual(row['reused_result_from_cell'],'1_r1_fixed')
        self.assertEqual(row['memory_policy'],'classifier')
        self.assertEqual(requests,[])

    def test_profiles_share_reanalysis_and_plan_then_change_only_generation(self):
        study=batch.Batch.__new__(batch.Batch);study.kind='profiles';study.context=threading.local()
        study.by_id={'1':{'index':1,'family_id':'family'}};study.profile_prefixes={}
        events=[]
        def request_for(namespace):
            def request(prompt):
                events.append((namespace,str(prompt)))
                return {'model':'offline-fixture','choices':[{'message':{'content':'{}'}}]}
            return request
        study.io=SimpleNamespace(request_for=request_for,save=lambda *args:None)
        start={'selected_cards':[],'retrieval_trace':{'status':'completed'},'query':{'public':'only'},'initial_analysis':{}}
        study.start=lambda *args,**kwargs:copy.deepcopy(start)
        def run_one(*args,**kwargs):
            request=args[3];cards,trace=kwargs['retrieval_provider'](start['query'])
            request('common reanalysis');request('common plan')
            request(batch.wiring.GENERATION+'\nAdopted experiences: []\nPlan: {}')
            return {'task_id':'1','attempts':[{'code':'fixture'}]}
        with patch.object(batch.runner,'run_one',side_effect=run_one):
            for arm in ('P00','P13','P22'):
                study.one({'task_id':'1','condition':arm,'repeat':1,'cell_id':'1_r1_'+arm})
        common=[p for namespace,p in events if namespace.startswith('shared_profile_prefix_')]
        generated=[p for namespace,p in events if not namespace.startswith('shared_profile_prefix_')]
        self.assertEqual(common,['common reanalysis','common plan'])
        self.assertEqual(len(generated),3)
        self.assertEqual(generated[0],batch.wiring.GENERATION+'\nAdopted experiences: []\nPlan: {}')
        self.assertTrue(all(p.startswith(generated[0]) for p in generated))
        self.assertNotEqual(generated[1],generated[2])

    def test_fast_exact_family_permutation_matches_original_enumeration(self):
        from methods.cle_ablation.run_memory_q_equal_k import exact_family_sign_flip
        for deltas in ([1,.5,0,-1],[.5,.5,-.5],[0,0],[1]*4):
            observed=abs(sum(deltas))
            brute=sum(abs(sum(s*d for s,d in zip(signs,deltas)))>=observed-1e-12
                      for signs in itertools.product((-1,1),repeat=len(deltas)))/2**len(deltas)
            self.assertEqual(exact_family_sign_flip(deltas),brute)

    def test_public_consumer_delivered_code_is_selected_attempt_not_last(self):
        row={'selected_attempt':0,'attempts':[{'code':'first'},{'code':'last'}],
             'final':{'measured':True,'joint':True}}
        self.assertEqual(policies.final(row)['code'],'first')
        self.assertNotIn('code',row['final'])

    def test_shared_Q_inputs_do_not_pass_on_a_partial_pair(self):
        from configs.cle_v41_completion_20261026.diagnostics import common_inputs
        trace={'status':'completed','query_hash':'same','candidate_ids':['a'],
               'scores':[{'id':'a','cosine':.8}]}
        rows=[{'task_id':'1','repeat':1,'cell_id':'one','retrieval_trace':trace}]
        result=common_inputs(rows,False)
        self.assertTrue(result['observed_common_inputs_match'])
        self.assertFalse(result['all_common_inputs_match'])
        self.assertFalse(result['complete'])

    def test_paid_pause_prevents_live_constructor_before_client_creation(self):
        with patch.object(batch,'read',return_value={'paid_execution_enabled':False}),patch.object(Path,'exists',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'paid_execution_paused'):
                batch.Batch({'id':'fixture','kind':'views'})

    def test_public_replay_ignores_only_temporary_path_and_keeps_saved_feedback(self):
        from methods.sct_trajectory.public_repair_policy import bind_public_result
        suite={'cases':[{'id':'f1','kind':'functional','purpose':'fixture','code':'assert False'}]}
        code='def f(): return 1'
        def result(path,status='fail'):
            return {'source':'self_generated_internal','backend':'local','cases':[
                {'id':'f1','kind':'functional','purpose':'fixture','measured':True,'status':status,
                 'error':path+'/worker.py AssertionError'}]}
        saved=bind_public_result(code,suite,result('case_saved'))
        study=batch.Batch.__new__(batch.Batch)
        study.replay_rows={'cell':{'internal_suite':suite,'attempts':[{'code':code,'internal_checks':saved}]}}
        study.io=SimpleNamespace(save=lambda *args:None)
        with patch('methods.sct_trajectory.internal_checks.execute_checks',return_value=result('case_current')):
            actual=study.public_replay_executor('cell')(code,'f',suite,backend='local',timeout=10)
        self.assertEqual(actual,saved)
        with patch('methods.sct_trajectory.internal_checks.execute_checks',return_value=result('case_current','pass')):
            with self.assertRaisesRegex(batch.ReplayStop,'check_result_differed'):
                study.public_replay_executor('cell')(code,'f',suite,backend='local',timeout=10)


    def test_resume_reuses_only_temporary_worker_path_difference(self):
        import tempfile
        from methods.sct_trajectory.replay_journal import RequestJournal
        settings={'model':'deepseek-v4.1-flash-1017'}
        old={'identity':'saved-000001','status':'completed','settings':settings,
             'selector':False,'prompt':r'error case_old\\worker.py assertion failed',
             'response':{'content':'saved code'}}
        with tempfile.TemporaryDirectory() as folder:
            def no_client():raise AssertionError('must not dispatch')
            for mode in ('resume', 'replay'):
                for changed in (False,True):
                    journal=RequestJournal(Path(folder)/mode/str(changed),mode=mode)
                    journal.records={old['identity']:old};journal.prior={old['identity']}
                    call=journal.wrap(no_client,settings)
                    prompt=r'error case_new\\worker.py assertion failed'+(' changed' if changed else '')
                    if changed:
                        error='resume_diverged' if mode=='resume' else 'replay_missing_request'
                        with self.assertRaisesRegex(batch.ReplayStop,error):call(prompt)
                    else:self.assertEqual(call(prompt),old['response'])


    def test_live_public_resume_restores_feedback_before_retrieval(self):
        import tempfile,json
        from methods.sct_trajectory.public_repair_policy import bind_public_result
        suite={'cases':[{'id':'f1','kind':'functional','purpose':'fixture','code':'assert False'}]}
        code='def f(): return 1'
        def result(path):
            return {'source':'self_generated_internal','backend':'local','cases':[
                {'id':'f1','kind':'functional','purpose':'fixture','measured':True,'status':'fail',
                 'error':path+'/worker.py AssertionError'}]}
        saved=bind_public_result(code,suite,result('case_saved'))
        with tempfile.TemporaryDirectory() as folder:
            prior=Path(folder);path=prior/'journals/cell/requests/old.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'prompt':'Permitted execution feedback: '+json.dumps({'internal_checks':saved})}),encoding='utf-8')
            study=batch.Batch.__new__(batch.Batch);study.prior=[prior]
            study.io=SimpleNamespace(save=lambda *args:None)
            with patch('methods.sct_trajectory.internal_checks.execute_checks',return_value=result('case_current')):
                restored=study.public_resume_executor('cell')(code,'f',suite,backend='local',timeout=10)
            self.assertEqual(restored,saved)
            from methods.sct_trajectory.public_repair_policy import public_repair_feedback
            legacy=public_repair_feedback(suite,saved,{})
            path.write_text(json.dumps({'prompt':'Permitted execution feedback: '+json.dumps(legacy)}),encoding='utf-8')
            with patch('methods.sct_trajectory.internal_checks.execute_checks',return_value=result('case_current')):
                restored=study.public_resume_executor('cell')(code,'f',suite,backend='local',timeout=10)
            self.assertEqual(restored,saved)


if __name__=='__main__':unittest.main()
