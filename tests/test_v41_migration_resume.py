import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from configs.cle_v41_migration_20261025.resume import RecoveryBudget,make_prefix_journal
from methods.sct_trajectory.replay_journal import RequestJournal,ReplayStop


class RecoveryTests(unittest.TestCase):
    def test_concurrent_budget_writes_and_settled_refund(self):
        with tempfile.TemporaryDirectory() as d:
            b=RecoveryBudget(Path(d)/'budget.json',[],max_tokens=100_000,max_calls=20)
            body={'model':'deepseek-v4.1-flash-1017','max_tokens':4096}
            def one(_):
                e=b.reserve(body)
                b.settle(e,b'data: {"usage":{"total_tokens":11}}\n')
            with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(one,range(16)))
            self.assertEqual(b.charged(),176)
            self.assertEqual(json.loads((Path(d)/'budget.json').read_text())['transport_attempts_including_prior'],16)

    def test_unknown_keeps_full_bound_and_hard_cap(self):
        with tempfile.TemporaryDirectory() as d:
            b=RecoveryBudget(Path(d)/'budget.json',[],max_tokens=6000)
            e=b.reserve({'model':'test','max_tokens':4096});b.settle(e,b'no usage')
            self.assertEqual(b.charged(),e['bound'])
            with self.assertRaisesRegex(RuntimeError,'budget_exhausted'):
                b.reserve({'model':'test','max_tokens':4096})

    def test_exact_prefix_reused_then_new_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);settings={'model':'test'}
            j=RequestJournal(root/'old');j.wrap(lambda:lambda p:{'value':'old'},settings)('prefix')
            new=Mock(return_value={'value':'new'})
            resumed=make_prefix_journal(RequestJournal,root/'new',[root/'old']).wrap(lambda:new,settings)
            self.assertEqual(resumed('prefix'),{'value':'old'});new.assert_not_called()
            self.assertEqual(resumed('next'),{'value':'new'});new.assert_called_once_with('next')
            self.assertEqual(len(list((root/'new').glob('*.json'))),1)

    def test_diverged_prefix_and_unresolved_request_never_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);settings={'model':'test'}
            j=RequestJournal(root/'old');j.wrap(lambda:lambda p:{'value':'old'},settings)('prefix')
            new=Mock()
            call=make_prefix_journal(RequestJournal,root/'new',[root/'old']).wrap(lambda:new,settings)
            with self.assertRaises(ReplayStop):call('different prompt')
            new.assert_not_called()
            p=next((root/'old').glob('*.json'));record=json.loads(p.read_text());record['status']='prepared'
            p.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError,'unresolved_prior'):
                make_prefix_journal(RequestJournal,root/'another',[root/'old'])


if __name__=='__main__':unittest.main()
