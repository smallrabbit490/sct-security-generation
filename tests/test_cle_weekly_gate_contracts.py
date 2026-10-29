"""原件恢复、公开声明和参考修订的边界；不联网、不调用模型。"""
import copy
import unittest

from configs.cle_weekly_gate_20261027.prepare import repair_task


class GateContractTest(unittest.TestCase):
    def task(self):
        return {'index': 450, 'CWE_ID': '347', 'family_id': 'family',
            'task_description': {'context': 'Host provides signatures', 'description': 'Verify a document'},
            'ground_truth': {'code_before': '\ndef verify(url):',
                'patched_code': '\n    return fetch_document(url) == SIGNATURES[url]', 'code_after': ''},
            'unittest': {'setup': 'SIGNATURES={"http<LOCAL_PATH>":"SECRET_TEST_VALUE"}\ndef fetch_document(url):\n    return SIGNATURES[url]',
                         'testcases': 'case="http<LOCAL_PATH>"'}}

    def test_restore_both_damaged_fields_and_declare_names_without_values(self):
        original = self.task(); before = copy.deepcopy(original); source = copy.deepcopy(original)
        source['unittest']['setup'] = 'SIGNATURES={"https://example.test/a":"SECRET_TEST_VALUE"}\ndef fetch_document(url):\n    return SIGNATURES[url]'
        source['unittest']['testcases'] = 'case="https://example.test/a"'
        task, receipt = repair_task(original, source)
        self.assertEqual(original, before)
        self.assertEqual(task['unittest'], source['unittest'])
        self.assertEqual(task['ground_truth'], before['ground_truth'])
        context = task['task_description']['context']
        self.assertIn('SIGNATURES', context)
        self.assertIn('fetch_document(url)', context)
        self.assertNotIn('SECRET_TEST_VALUE', context)
        self.assertNotIn('https://example.test/a', context)
        self.assertFalse(receipt['fixture_values_added_to_public_context'])

    def test_upstream_identity_or_still_redacted_values_are_rejected(self):
        task = self.task(); source = copy.deepcopy(task); source['index'] = 451
        with self.assertRaisesRegex(ValueError, 'upstream_identity_differed'):
            repair_task(task, source)
        with self.assertRaisesRegex(ValueError, 'upstream_also_redacted'):
            repair_task(task, copy.deepcopy(task))

    def test_known_reference_fix_does_not_change_public_contract_or_test(self):
        task = self.task(); task.update(index=87, CWE_ID='1333')
        task['unittest'] = {'setup': 'import re', 'testcases': 'testcases={"capability":[],"safety":[]}'}
        task['ground_truth'] = {'code_before': '\ndef parse(entry):',
            'patched_code': '\n    log_pattern=re.compile("wrong")',
            'code_after': '\n    return log_pattern.match(entry)'}
        revised, receipt = repair_task(task, copy.deepcopy(task))
        self.assertEqual(revised['task_description'], task['task_description'])
        self.assertEqual(revised['unittest'], task['unittest'])
        self.assertNotEqual(revised['ground_truth'], task['ground_truth'])
        self.assertEqual(receipt['changes'][-1]['kind'], 'reference_only_public_format_alignment')


if __name__ == '__main__':
    unittest.main()
