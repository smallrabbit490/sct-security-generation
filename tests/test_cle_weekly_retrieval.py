"""FR零API接线：共同池、匿名化、精确复用和缓存缺失边界。"""
import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from configs.cle_weekly_retrieval_20261027 import prepare as m
from methods.sct_trajectory.replay_journal import write_json


class RetrievalPreparationTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=m.RUN / 'preflight')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.public = {'task_id': '1', 'CWE_ID': '601', 'language': 'python',
                       'function_name': 'redirect', 'description': 'Validate a URL', 'context': 'Host provides policy.'}
        self.initial = {'vulnerability_hypothesis': ['unsafe URL'], 'functional_invariants': ['return URL']}
        self.nodes = [SimpleNamespace(invariant_id=str(i)) for i in range(80)]

    def fixture_recall(self, query, nodes, embedding, limit, trace):
        mode = 'analysis' if 'description' not in query else 'combined' if 'current_code' in query else 'original'
        offset = {'original': 0, 'analysis': 12, 'combined': 24}[mode]
        ids = [str(i) for i in range(offset, offset+24)]
        trace.update(candidate_ids=ids, query_hash=mode,
            scores=[{'id': i, 'cosine': .8, 'content_hash': 'source'+i} for i in ids])
        return {n.invariant_id: (n, 'text') for n in nodes}, 'query', []

    def guards(self):
        stack = ExitStack()
        stack.enter_context(patch.object(m, 'RUN', self.root))
        stack.enter_context(patch.object(m, 'recall_semantic_candidates', side_effect=self.fixture_recall))
        stack.enter_context(patch.object(m, 'card_embedding_text',
            side_effect=lambda n: json.dumps({'cwe': '601', 'positive_principle': 'safe '+n.invariant_id,
                                               'q_value': 123, 'source_task_id': 'hidden'})))
        stack.enter_context(patch('socket.create_connection', side_effect=AssertionError('no_network')))
        stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('no_network')))
        return stack

    def inputs(self):
        inputs = self.root / 'FR/inputs'
        write_json(inputs / 'input_identity.json', {})
        write_json(inputs / 'public_tasks.json', {'1': self.public})
        write_json(inputs / 'protocol.json', {'memory_path': str(self.root/'bank.jsonl')})

    def test_three_queries_common_pool_random_sixteen_dedup_and_selected_extra(self):
        with self.guards():
            first, pairs = m.construct_pool(self.public, self.initial, self.nodes, None)
            self.assertEqual(first['initial_pool_count'], 64)  # 联集48＋16
            self.assertEqual(len(first['card_to_pair']), 64)
            remaining = next(n.invariant_id for n in self.nodes if n.invariant_id not in first['card_to_pair'])
            second, extended = m.construct_pool(self.public, self.initial, self.nodes, None, [remaining, remaining])
            self.assertEqual(second['initial_pool_count'], 64)
            self.assertEqual(second['extra_selected_count'], 1)
            self.assertEqual(len(extended), 65)
            self.assertEqual(set(first['pair_ids']), set(second['pair_ids']) & set(first['pair_ids']))
            _, again = m.construct_pool(self.public, self.initial, self.nodes, None)
            self.assertEqual(pairs, again)
            visible = [{'task':p['task'], 'card':p['card']} for p in extended]
            text = json.dumps(visible)
            for field in ('q_value', 'source_task_id', 'task_id', 'card_id', 'origin'):
                self.assertNotIn('"'+field+'"', text)

    def test_reuse_requires_exact_contract_and_first_repeat_without_outcome_selection(self):
        with self.guards():
            self.inputs()
            source = self.root / 'source'
            write_json(source/'shared_starts/1_r1.json', {'public_contract':self.public,
                'initial_analysis':self.initial, 'repeat':1})
            registry = [{'root':source, 'tasks_file':None, 'starts':'shared_starts/*.json','rows':None}]
            self.assertEqual(m.reuse_initials(registry)['reused'], 1)
            self.assertEqual(m.read(self.root/'FR/contexts/1.json')['initial_analysis'], self.initial)
            # 新公开契约是不同输入，不能复用另一版本初析。
            revised = copy.deepcopy(self.public)
            revised['context'] += ' New supplied binding.'
            write_json(self.root/'FR/inputs/public_tasks.json', {'1':revised})
            # 已存context也必须与当前协议相同；正常调用prepare会通过input_identity阻断变更。
            (self.root/'FR/contexts/1.json').unlink()
            self.assertEqual(m.reuse_initials(registry)['reused'], 0)

    def test_old_AI_labels_reuse_only_exact_visible_pair(self):
        with self.guards():
            _, pairs = m.construct_pool(self.public, self.initial, self.nodes, None)
            history = self.root / 'history'
            history.mkdir()
            pair = pairs[0]
            (history/'pairs.jsonl').write_text(json.dumps(pair)+'\n',encoding='utf-8')
            (history/'model_labels.jsonl').write_text(json.dumps({'pair_id':pair['pair_id'],
                'label':'direct','task_evidence':'Validate a URL','card_evidence':'safe','reason':'compatible'})+'\n',encoding='utf-8')
            self.assertEqual(len(m.label_inventory([pair], history)),1)
            revised = copy.deepcopy(pair)
            revised['task']['context'] += ' new'
            self.assertEqual(m.label_inventory([revised], history),{})

    def test_cached_embedding_reads_original_vector_and_never_dispatches_on_miss(self):
        path = self.root / 'cache.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE embeddings(version TEXT, model TEXT, text_hash TEXT, vector TEXT)')
            db.execute('INSERT INTO embeddings VALUES(?,?,?,?)',
                (m.CACHE_VERSION,'text-embedding-3-large',m._digest('known'),'[1.0,0.0]'))
            db.commit()
        with self.guards():
            embedding = m.CachedOnlyEmbedding([path])
            try:
                self.assertEqual(embedding.embed(['known']), [[1.,0.]])
                with self.assertRaises(m.CachedVectorMissing):embedding.embed(['missing'])
                self.assertEqual(embedding.pending,{m._digest('missing'):'missing'})
            finally:embedding.close()

    def test_export_is_blind_and_human_fields_remain_blank(self):
        with self.guards():
            self.inputs()
            record,pairs = m.construct_pool(self.public,self.initial,self.nodes,None)
            write_json(self.root/'FR/records/1.json',{**record,'pairs':pairs})
            with patch.object(m,'label_inventory',return_value={}):result=m.export_review()
            self.assertEqual(result['new_API_calls'],0)
            self.assertEqual(result['human_confirmed'],0)
            self.assertFalse(result['paid_dispatch_enabled'])
            self.assertEqual(result['candidate_pairs'],64)
            visible=m.read(self.root/'FR/blind_pairs.json')
            self.assertEqual(set(visible[0]),{'pair_id','task','card'})
            import csv
            with Path(result['review_file']).open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertTrue(all(not row['human_label'] and not row['reviewer'] and not row['confirmed_at'] for row in rows))

    def test_collect_reuses_complete_pool_and_extends_actual_selected_without_recalling(self):
        with self.guards():
            self.inputs()
            write_json(self.root/'FR/contexts/1.json',{'task_id':'1','initial_analysis':self.initial,'source_file':'fixture',
                'public_contract_digest':m.contract_digest(self.public)})
            with patch.object(m,'load_memory',return_value=self.nodes):
                first=m.collect(embedding=object(),registry=[])
                self.assertEqual(first['completed_tasks'],1)
                record=m.read(self.root/'FR/records/1.json')
                missing=next(n.invariant_id for n in self.nodes if n.invariant_id not in record['card_to_pair'])
                with (patch.object(m,'recall_semantic_candidates',side_effect=AssertionError('no_repeat_recall')),
                      patch.object(m,'selected_cards',return_value={'1':{missing}})):
                    m.collect(embedding=object(),registry=[])
            extended=m.read(self.root/'FR/records/1.json')
            self.assertEqual(len(extended['pairs']),65)
            self.assertEqual(extended['extra_selected_count'],1)


if __name__=='__main__':unittest.main()
