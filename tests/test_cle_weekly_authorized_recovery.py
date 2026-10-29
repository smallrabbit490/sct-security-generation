"""只豁免人类指定的437原失败请求；其余未决及费用边界保持。"""
from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from configs.cle_weekly_recovery_20261027 import recover
from methods.sct_trajectory.selector_protocol import SelectorPrompt


class AuthorizedRecoveryTest(unittest.TestCase):
    def test_only_specific_old_path_is_exempt_not_next_segment_failure(self):
        later = recover.ORIGINAL.parent/'segment_002/journals'/recover.CELL/'requests'/(recover.IDENTITY+'.json')
        unrelated = recover.ORIGINAL/'journals/K0_other/requests/pending.json'
        paths = list(map(str, (recover.FAILED_REQUEST, later, unrelated)))
        with patch.object(recover, 'ORIGINAL_UNRESOLVED', return_value=paths):
            self.assertEqual(recover.approved_unresolved([]), paths[1:])

    def test_next_selector_identity_matches_exact_authorized_prompt(self):
        old = recover.learn.read(recover.FAILED_REQUEST)
        prompt = SelectorPrompt(old['prompt'], deadline=1e20)
        journal = SimpleNamespace(counts=Counter())
        identity, public = recover.request_identity(journal, prompt)
        self.assertEqual(identity, recover.IDENTITY)
        self.assertEqual(public, {key: old[key] for key in ('settings', 'prompt', 'selector')})
        changed, _ = recover.request_identity(journal, SelectorPrompt(old['prompt']+'different', deadline=1e20))
        self.assertNotEqual(changed, recover.IDENTITY)

    def test_real_zero_API_prefix_and_old_unknown_charge_are_preserved(self):
        result = recover.learn.read(recover.ORIGINAL.parent/'authorized_prefix_probe_20261027/prefix_probe_result.json')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['completed_prefix_tasks'], 63)
        self.assertEqual(result['task437_saved_logical_responses_consumed'], 6)
        self.assertEqual(result['new_HTTP'], 0)
        self.assertEqual(recover.learn.read(recover.FAILED_REQUEST)['status'], 'failed_or_unresolved')
        receipt = recover.learn.read(recover.AUTHORIZATION)
        self.assertEqual(receipt['old_execution_or_charge'], 'unknown')
        self.assertFalse(receipt['budget_reset'])


if __name__ == '__main__':
    unittest.main()
