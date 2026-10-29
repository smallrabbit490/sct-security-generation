"""FR付费层仅用合成HTTP回放测试：一次盲标、累计预算、缺卡批量、停止和恢复。"""
import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from configs.cle_weekly_retrieval_20261027 import execute as m
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


class HTTPReply(io.BytesIO):
    status = 200


class RetrievalExecutionTest(unittest.TestCase):
    def test_policy_gate_process_also_queues_retrieval_calls(self):
        result = SimpleNamespace(stdout=json.dumps([{'ProcessId': 123,
            'CommandLine': 'python -m configs.cle_weekly_granularity_gate_20261027.evaluate run --workers 3'}]))
        with patch.object(m.subprocess, 'run', return_value=result):
            self.assertEqual(m.active_evaluations(), [123])

    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=m.prep.RUN / 'preflight')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.task = {'task_id': '1', 'language': 'python', 'CWE_ID': '601',
                     'description': 'Validate URL before redirect', 'function_name': 'redirect'}
        self.initial = {'vulnerability_hypothesis': ['unsafe target'], 'functional_invariants': ['return allowed URL']}
        self.nodes = [SimpleNamespace(invariant_id=i, status='active', language_leaves={'python': {}},
            source={}, cwe='601', high_level_invariant='safe URL', applicability='URL',
            positive_principle='Validate '+i, negative_guardrail='no unsafe host', track_rules=[]) for i in ('a', 'b')]
        self.calls = []

    def fake_recall(self, task, nodes, embedding, limit, trace):
        trace.update(candidate_ids=['a', 'b'], scores=[{'id':'a','cosine':.9},{'id':'b','cosine':.8}], query_hash='fixture')
        return {n.invariant_id:(n, m.card_embedding_text(n)) for n in nodes}, 'fixture', []

    def guards(self):
        stack = ExitStack()
        for target, value in [('RUN', self.root)]:
            stack.enter_context(patch.object(m.prep, target, value))
        stack.enter_context(patch.object(m.prep, 'prepare', return_value={}))
        stack.enter_context(patch.object(m.prep, 'verify', return_value=None))
        stack.enter_context(patch.object(m.prep, 'load_memory', return_value=self.nodes))
        stack.enter_context(patch.object(m.prep, 'source_registry', return_value=[]))
        stack.enter_context(patch.object(m.prep, 'cache_sources', return_value=[]))
        stack.enter_context(patch.object(m.prep, 'recall_semantic_candidates', side_effect=self.fake_recall))
        stack.enter_context(patch.object(m, 'active_evaluations', return_value=[]))
        for target in ('configs.cle_v41_relation_20261026.execution.ensure_model_call_allowed',
                       'methods.sct_trajectory.replay_journal.ensure_model_call_allowed',
                       'methods.sct_trajectory.run_closed_loop.ensure_model_call_allowed'):
            stack.enter_context(patch(target, return_value=None))
        stack.enter_context(patch('methods.sct_trajectory.run_closed_loop.load_key', return_value='synthetic-test-key'))
        stack.enter_context(patch('socket.create_connection', side_effect=AssertionError('no_real_network')))
        stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('no_real_network')))
        return stack

    def inputs(self):
        target = self.root / 'FR/inputs'
        write_json(target/'public_tasks.json', {'1':self.task})
        write_json(target/'input_identity.json', {})
        write_json(target/'manifest.json', [{'task_id':'1','pool':'D_gate','family_id':'fixture'}])
        write_json(target/'protocol.json', {'memory_path':str(self.root/'bank.jsonl')})
        write_json(self.root/'FR/contexts/1.json', {'task_id':'1', 'public_contract_digest':m.prep.contract_digest(self.task),
            'initial_analysis':self.initial,'source_file':'saved-real-in-production-fixture-only-here'})
        self.root.joinpath('bank.jsonl').write_text('fixture', encoding='utf-8')

    def transport(self, request, **kwargs):
        body = json.loads(request.data)
        self.calls.append(body)
        if body['model'] == 'text-embedding-3-large':
            return HTTPReply(json.dumps({'data':[{'index':i,'embedding':[1.,float(i+1)]} for i in range(len(body['input']))],
                'usage':{'prompt_tokens':10,'total_tokens':10}}).encode())
        content = json.dumps({'label':'direct','task_evidence':'Validate URL', 'card_evidence':'Validate', 'reason':'Applicable'})
        return self.model_reply(content)

    def model_reply(self, content):
        payload = {'model':m.MODEL,'choices':[{'index':0,'delta':{'role':'assistant','content':content},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
        return HTTPReply(('data: '+json.dumps(payload)+'\n\ndata: [DONE]\n\n').encode())

    def worker(self, sources=(), physical=None):
        return m.RetrievalExecution(sources, physical_open=physical or self.transport)

    def test_budget_is_finite_and_covers_registered_extra_pairs(self):
        with self.guards():
            self.inputs()
            protocol = m.prepare()
            self.assertEqual(protocol['pair_limit'],107821)
            self.assertEqual(protocol['extra_pair_cap'],43869)
            self.assertEqual(protocol['embedding_text_limit'],3652)
            self.assertEqual(protocol['AI_max_attempts'],1)
            self.assertLess(protocol['pair_limit'],protocol['absolute_task_card_upper_bound'])
            self.assertGreater(protocol['budget_proposed']['conservative_model_and_embedding_tokens'],0)

    def test_batch_embeddings_blind_pair_once_and_completed_resume_no_HTTP(self):
        with self.guards():
            self.inputs()
            first = self.worker()
            result = first.execute()
            self.assertEqual(result['status'],'awaiting_human_confirmation')
            self.assertEqual(len(self.calls),3)
            embeddings = [c for c in self.calls if c['model']=='text-embedding-3-large']
            self.assertEqual(len(embeddings),1)  # 全卡与三查询缺项一次原生批量处理
            self.assertEqual(len(embeddings[0]['input']),5)
            for call in self.calls[1:]:
                text=call['messages'][0]['content']
                for field in ('invariant_id','q_value','selected_ids','joint','task_id'):
                    self.assertNotIn('"'+field+'"',text)
                self.assertEqual(call['max_tokens'],4096)
                self.assertEqual([v['role'] for v in call['messages']],['user'])
            second = self.worker([first.root])
            resumed = second.execute()
            self.assertEqual(resumed['new_physical_HTTP'],0)
            self.assertEqual(resumed['budget']['transport_attempts_including_prior'],3)
            self.assertEqual(len(self.calls),3)
            write_json(self.root/'FR/execution_index.json',{'segments':[str(first.root),str(second.root)]})
            replay=m.replay()
            self.assertEqual(replay['status'],'passed')
            self.assertEqual(replay['completed_AI_responses_replayed'],2)
            self.assertEqual(replay['candidate_task_pools_replayed'],1)
            self.assertEqual(len(self.calls),3)

    def test_completed_malformed_label_is_error_and_never_retried(self):
        with self.guards():
            self.inputs()
            def malformed(request,**kwargs):
                body=json.loads(request.data)
                if body['model']=='text-embedding-3-large':
                    return self.transport(request,**kwargs)
                self.calls.append(body)
                return self.model_reply('not a label object')
            first=self.worker(physical=malformed)
            result=first.execute()
            self.assertEqual(result['AI_label_errors'],2)
            second=self.worker([first.root],physical=malformed)
            resumed=second.execute()
            self.assertEqual(resumed['AI_label_errors'],2)
            self.assertEqual(resumed['new_physical_HTTP'],0)
            self.assertEqual(len(self.calls),3)

    def test_transport_failure_stops_next_pair_and_unresolved_resume_is_blocked(self):
        with self.guards():
            self.inputs()
            def failed(request,**kwargs):
                body=json.loads(request.data)
                if body['model']=='text-embedding-3-large':
                    return self.transport(request,**kwargs)
                self.calls.append(body)
                raise urllib.error.URLError('synthetic transport failure')
            first=self.worker(physical=failed)
            result=first.execute()
            self.assertEqual(result['status'],'stopped_technical')
            self.assertEqual(len(self.calls),2)
            self.assertEqual(len(m.unresolved([first.root])),1)
            self.assertEqual(result['budget']['entries'][-1]['status'],'failed_unknown')
            with self.assertRaises(ReplayStop):self.worker([first.root])
            self.assertEqual(len(self.calls),2)

    def test_saved_response_without_saved_label_recovers_response_no_repurchase(self):
        with self.guards():
            self.inputs()
            first=self.worker()
            original=first.io.save
            def fail_label(name,value):
                if name.startswith('labels/'):
                    raise OSError('synthetic local label persistence failure')
                return original(name,value)
            with patch.object(first.io,'save',side_effect=fail_label):
                result=first.execute()
            self.assertEqual(result['status'],'stopped_technical')
            self.assertEqual(len(self.calls),2)
            self.assertFalse(m.unresolved([first.root]))
            second=self.worker([first.root])
            resumed=second.execute()
            self.assertEqual(resumed['status'],'awaiting_human_confirmation')
            self.assertEqual(resumed['new_physical_HTTP'],1)  # 第一对消费原响应，仅第二对新请求
            self.assertEqual(len(self.calls),3)

    def test_check_queues_active_four_worker_without_dispatch(self):
        with self.guards():
            self.inputs()
            write_json(self.root/'FR/execution_offline_checks.json',{'status':'passed'})
            with patch.object(m,'active_evaluations',return_value=[1234]),patch.object(m,'ensure_model_call_allowed'):
                result=m.launch()
            self.assertEqual(result['status'],'queued_no_process_started')
            self.assertIn('queued_behind_active_four_worker_evaluation',result['reasons'])
            self.assertEqual(self.calls,[])

    def test_check_keeps_forbidden_time_zero_API(self):
        with self.guards():
            self.inputs()
            write_json(self.root/'FR/execution_offline_checks.json',{'status':'passed'})
            with patch.object(m,'ensure_model_call_allowed',side_effect=m.ModelTimeWindowError('forbidden fixture')):
                result=m.launch()
            self.assertIn('waiting_allowed_time_window',result['reasons'])
            self.assertEqual(result['status'],'queued_no_process_started')
            self.assertEqual(self.calls,[])

    def test_human_review_requires_actual_adjudication_no_AI_auto_signature(self):
        with self.guards():
            self.inputs()
            first=self.worker()
            first.execute()
            review=Path(m.export_human([first.root])['review_file'])
            import csv
            with review.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertTrue(all(not r['human_label'] and not r['reviewer'] and not r['confirmed_at'] for r in rows))
            with self.assertRaises(ValueError):m.import_review(review)
            self.assertFalse((self.root/'FR/human_labels.json').exists())
            result=m.summarize([first.root])
            self.assertEqual(result['formal_metrics'],'pending_human_confirmation')
            self.assertEqual(result['full_library_recall'],'unmeasured')

    def test_four_metrics_use_actual_native_selection_not_numerical_top_three(self):
        with self.guards():
            self.inputs()
            first=self.worker()
            first.execute()
            actual=[{'task_id':'1','package':'FQ_GATE','condition':'Q2','repeat':1,
                'cell_id':'1_r1_Q2','selected_ids':['a'],'technical_error':False}]
            with patch.object(m.prep,'selected_cards',return_value=actual):
                summary=m.summarize([first.root])
            metric=summary['native_first_selection_metrics']['FQ_GATE:Q2:r1']['model_assisted_candidate_pool_metrics']
            self.assertEqual(metric['counts']['TP'],1)
            self.assertEqual(metric['counts']['FN'],1)
            self.assertEqual(metric['precision'],1.)
            self.assertEqual(metric['recall'],.5)
            self.assertAlmostEqual(metric['f1'],2/3)
            self.assertEqual(summary['formal_metrics'],'pending_human_confirmation')


if __name__=='__main__':unittest.main()
