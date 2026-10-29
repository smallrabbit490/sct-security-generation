"""D_grow新评价契约只修已知问题，保留学习输入、题族和验收规则。"""
import copy
import unittest

from configs.cle_weekly_contracts_20261027.grow import repair_task
from tests import test_cle_weekly_gate_contracts as gate_fixture


class GrowContractsTest(unittest.TestCase):
    def test_placeholder_restore_only_and_no_test_value_in_public(self):
        task = gate_fixture.GateContractTest().task()
        task['index'] = 1301
        source = copy.deepcopy(task)
        source['unittest']['setup'] = source['unittest']['setup'].replace('http<LOCAL_PATH>', 'https://source.test/a')
        source['unittest']['testcases'] = source['unittest']['testcases'].replace('http<LOCAL_PATH>', 'https://source.test/a')
        before = copy.deepcopy(task)
        revised, _ = repair_task(task, source)
        self.assertEqual(task, before)
        self.assertEqual(revised['unittest'], source['unittest'])
        self.assertNotIn('SECRET_TEST_VALUE', str(revised['task_description']))
        self.assertNotIn('https://source.test/a', str(revised['task_description']))

    def test_logs_reference_only_and_family_unchanged(self):
        task = gate_fixture.GateContractTest().task()
        task.update(index=84, CWE_ID='1333')
        task['ground_truth'] = {'code_before': '\ndef decode(entry):',
            'patched_code': '\n    log_pattern=re.compile("bad")', 'code_after': '\n    return log_pattern.match(entry)'}
        task['unittest'] = {'setup': 'import re', 'testcases': 'testcases={}'}
        before = copy.deepcopy(task)
        revised, _ = repair_task(task, copy.deepcopy(task))
        self.assertEqual(task, before)
        self.assertEqual(revised['task_description'], task['task_description'])
        self.assertEqual(revised['unittest'], task['unittest'])
        self.assertEqual(revised['family_id'], task['family_id'])
        self.assertNotEqual(revised['ground_truth'], task['ground_truth'])

    def test_email_reuses_known_reference_correction_no_new_test(self):
        task = gate_fixture.GateContractTest().task()
        task.update(index=108, CWE_ID='179')
        task['ground_truth'] = {'code_before': '\ndef validate(email):\n    local_part=email',
            'patched_code': "\n    if '..' in local_part:\n        return False", 'code_after': '\n    return True'}
        task['unittest'] = {'setup': '', 'testcases': 'testcases={}'}
        revised, _ = repair_task(task, copy.deepcopy(task))
        self.assertEqual(revised['unittest'], task['unittest'])
        self.assertEqual(revised['task_description'], task['task_description'])
        self.assertIn("local_part.startswith('.')", revised['ground_truth']['patched_code'])


if __name__ == '__main__':
    unittest.main()
