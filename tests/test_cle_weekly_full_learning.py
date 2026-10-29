"""新全量学习入口的零API集成：原P7和请求器，合成服务，不读取凭据。"""
import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_full_20261027 import learn as m
from configs.cle_v41_relation_20261026.offline_execution_check import Response
from configs.cle_v41_relation_20261026.offline_check import INITIAL
from configs.cle_v41_relation_20261026 import wiring
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


class WeeklyLearningTest(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(dir=m.RUN/'preflight')
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.bank=m.runner.load_memory(m.RUN/'shared_inputs/memory1939_q0.jsonl')[:2]
        for n in self.bank:n.q_value=0.;n.q_visits=0
        m.save_memory(self.root/'shared_inputs/memory1939_q0.jsonl',self.bank)
        tasks={str(i):{'index':i,'CWE_ID':'347','family_id':str(i),'task_description':{'description':f'Task {i}: load a file'}} for i in (1,2)}
        write_json(self.root/'shared_inputs/tasks_D_init.json',tasks)
        write_json(self.root/'manifest.json',{'pools':{'D_init':['1','2']}})
        write_json(self.root/'protocol.json',{'protocol':m.PROTOCOL,'paid_execution_enabled':True})
        write_json(self.root/'budget.json',{'stages':{'K0':{'tokens':10000000,'HTTP':100,'embedding_HTTP':20}}})
        write_json(self.root/'preflight/qualification.json',{'tasks':{str(i):{'reward_eligible':True} for i in (1,2)}})
        with closing(sqlite3.connect(self.root/'shared_inputs/embeddings.sqlite3')) as db:db.execute('CREATE TABLE fixture (id INTEGER)')
        self.http=[];self.generation=0;self.q_reads=[];self.stage=None

    def service(self,request,*args,**kwargs):
        body=json.loads(request.data);self.http.append(body)
        prompt=body['messages'][0]['content']
        if prompt.startswith('Select fixture'):content='{"selected":[1,2]}'
        elif prompt.startswith(wiring.GENERATION):
            self.generation+=1
            content=f'def load_file():\n    return {self.generation}\n'
        elif prompt.startswith('Plan the implementation.'):
            content=json.dumps({'Preserved_Func':'load file interface','Patch_Scope':'Preserve the public interface'})
        else:
            content=json.dumps({**INITIAL,'applied_experience_ids':[self.bank[0].invariant_id], 'rejected_experiences':[]})
        result={'model':wiring.SETTINGS['model'], 'choices':[{'index':0,'delta':{'content':content},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
        return Response(('data: '+json.dumps(result)+'\n\ndata: [DONE]\n\n').encode())

    def select(self,retriever,query,limit,pool_nodes):
        self.assertEqual(limit,3)
        self.q_reads.append([(n.q_value,n.q_visits) for n in pool_nodes])
        retriever.requester(SelectorPrompt('Select fixture',deadline=1e20))
        scores=[{'id':n.invariant_id,'cosine':.8-j*.1} for j,n in enumerate(pool_nodes)]
        ordered=rank_candidates(scores,{n.invariant_id:n.q_value for n in pool_nodes},delta=-1,lambda_q=.5,limit=None)
        retriever.last_hier_trace={'status':'completed','scores':scores,'selection_limit':3,
            'candidate_order':'q','presented_candidate_ids':[r['id'] for r in ordered]}
        return [{'invariant_id':n.invariant_id,'positive_principle':'Preserve the public interface'} for n in pool_nodes]

    def validate(self,task,code,timeout):
        status='fail' if 'return 1' in code else 'pass'
        return {'functional':{'status':status,'measured':True},'security':{'status':'pass','measured':True}}, 'A' if status=='pass' else 'B'

    def guards(self):
        stack=ExitStack()
        stack.enter_context(patch.object(m,'RUN',self.root))
        stack.enter_context(patch.object(m,'source_snapshot'))
        for target in ('methods.sct_trajectory.run_closed_loop.ensure_model_call_allowed',
                       'methods.sct_trajectory.replay_journal.ensure_model_call_allowed',
                       'configs.cle_v41_relation_20261026.execution.ensure_model_call_allowed'):
            stack.enter_context(patch(target,return_value=None))
        stack.enter_context(patch('methods.sct_trajectory.run_closed_loop.load_key',return_value='synthetic-offline-only'))
        stack.enter_context(patch('methods.sct_trajectory.closed_loop.validate_and_state',side_effect=self.validate))
        stack.enter_context(patch('methods.sct_trajectory.retriever.HskTreeRetriever.search',
            lambda obj,query,limit,pool_nodes:self.select(obj,query,limit,pool_nodes)))
        stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('network_forbidden')))
        stack.enter_context(patch('socket.socket.connect',side_effect=AssertionError('network_forbidden')))
        return stack

    def test_native_two_tasks_credit_boundary_early_stop_and_exact_replay(self):
        with self.guards():
            stage=m.LearningStage('K0','D_init')
            stage.io.physical_open=self.service
            result=stage.execute()
            self.assertEqual(result['completed'],2)
            self.assertEqual([len(r['attempts']) for r in stage.rows],[2,1])
            self.assertEqual(result['credited_events'],3)
            self.assertAlmostEqual(stage.bank[0].q_value,.363)
            self.assertEqual(stage.bank[0].q_visits,3)
            self.assertEqual(stage.bank[1].q_visits,0)
            self.assertEqual(self.q_reads[:2],[[(0.,0),(0.,0)]]*2)
            self.assertAlmostEqual(self.q_reads[2][0][0],.09)
            self.assertEqual(self.q_reads[2][0][1],2)
            self.assertEqual(result['physical_HTTP'],len(self.http))
            for body in self.http:
                self.assertEqual([x['role'] for x in body['messages']],['user'])
                self.assertEqual(body['model'],wiring.SETTINGS['model'])
                self.assertEqual(body['temperature'],0)
                self.assertEqual(body['thinking'],{'type':'disabled'})
                self.assertEqual(body['max_tokens'],256 if body['messages'][0]['content'].startswith('Select fixture') else 4096)
            paid=len(self.http)
            replay=m.LearningStage('K0','D_init',[stage.out],offline=True,destination=self.root/'replay')
            replay.execute()
            self.assertEqual(len(self.http),paid)
            self.assertEqual(m.read(replay.out/'replay_result.json')['status'],'passed')
            recovered=copy.deepcopy(self.bank)
            rows=m.restore_prefix(stage.cells,[stage.out],recovered,stage.eligibility)
            self.assertEqual(len(rows),2)
            self.assertAlmostEqual(recovered[0].q_value,.363)

    def test_ineligible_does_not_receive_reward_but_is_still_executed(self):
        with self.guards():
            stage=m.LearningStage('K0','D_init')
            stage.eligibility['2']['reward_eligible']=False
            stage.io.physical_open=self.service
            result=stage.execute()
            self.assertEqual(result['completed'],2)
            self.assertEqual(stage.bank[0].q_visits,2)
            self.assertAlmostEqual(stage.bank[0].q_value,.09)

    def test_incomplete_saved_request_is_never_redispatched(self):
        prior=self.root/'prior'
        write_json(prior/'journals/K0_1/requests/pending.json',{'status':'prepared'})
        with self.guards(),self.assertRaises(ReplayStop):
            m.LearningStage('K0','D_init',[prior])
        self.assertEqual(self.http,[])

    def test_native_swallowed_transport_failure_stops_before_credit_or_next_task(self):
        with self.guards():
            stage=m.LearningStage('K0','D_init')
            def failed_initial(task,request):
                stage.io.reason='logical_request_failed_or_unresolved'
                return {'initial_analysis':{'unmeasured':True},'error_type':'URLError'}
            with patch.object(m,'prepare_shared_initial',side_effect=failed_initial),self.assertRaises(ReplayStop):
                stage.execute()
            self.assertEqual(stage.rows,[])
            self.assertEqual(stage.bank[0].q_visits,0)
            self.assertEqual(m.read(stage.out/'state.json')['status'],'needs_technical_recovery')
            self.assertEqual(len(list((stage.out/'initials').glob('*.json'))),1)
        self.assertEqual(self.http,[])


if __name__=='__main__':unittest.main()
