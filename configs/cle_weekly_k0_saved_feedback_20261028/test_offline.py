"""本次真实回放分歧的有限离线检查；不构造任何网络客户端。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from methods.sct_trajectory.replay_journal import ReplayStop
from . import certificate, continuation
from .replay import HistoricalFeedback, audit_journals


class OfflineTests(unittest.TestCase):
    def test_feedback_rejects_different_code_and_extra_calls(self):
        task = {'task_index': 1}
        attempt = {'attempt': 0, 'code': 'x=1', 'validation': {
            'evidence': {'functional': {'status': 'fail'}, 'security': {'status': 'pass'}}, 'state': 'C'}}
        feedback = HistoricalFeedback([{'task_id': '1', 'attempts': [attempt]}], {'1': task})
        with self.assertRaises(ReplayStop):
            feedback(task, 'x=2')
        self.assertEqual(feedback(task, 'x=1')[1], 'C')
        with self.assertRaises(ReplayStop):
            feedback(task, 'x=1')

    def test_feedback_rejects_wrong_task(self):
        feedback = HistoricalFeedback([{'task_id': '1', 'attempts': [{'attempt': 0, 'code': 'x=1'}]}],
                                      {'1': {'task_index': 1}})
        with self.assertRaises(ReplayStop):
            feedback({'task_index': 2}, 'x=1')

    def test_missing_or_incomplete_certificate_never_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(certificate.accepted(root))
            target = root / certificate.RELATIVE / 'certificate.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({'status': certificate.STATUS}), encoding='utf-8')
            self.assertFalse(certificate.accepted(root))

    def test_only_authorized_K0_dependency_is_removed(self):
        original = lambda: {'ready': False, 'reasons': ['K0_native_replay_pending', 'K2_not_completed']}
        with patch.object(continuation, 'accepted', return_value=True):
            result = continuation.dependencies(original, Path('unused'))
        self.assertFalse(result['ready'])
        self.assertEqual(result['reasons'], ['K2_not_completed'])
        self.assertFalse(result['K0_dynamic_validation_all_consistent'])
        with patch.object(continuation, 'accepted', return_value=False):
            self.assertEqual(continuation.dependencies(original, Path('unused')), original())

    def test_corrupt_original_request_identity_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'journals/K0_1/requests/bad-000001.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({'settings': {}, 'prompt': 'x', 'selector': False,
                'identity': 'bad-000001', 'status': 'completed'}), encoding='utf-8')
            with self.assertRaises(ReplayStop):
                audit_journals([root])

    def test_future_native_launch_keeps_adapter_and_worker_allocation(self):
        command = ['python', '-B', '-m', continuation.NATIVE, 'run']
        def native_main():
            self.assertEqual(continuation.retest.FrozenRetest.worker_limit, 3)
            subprocess.Popen(command)
        with patch.object(sys, 'argv', ['continuation', 'launch', '--workers', '3']), \
                patch('tools.cle_live_workbench.app.process_inventory', return_value=[]), \
                patch.object(continuation.retest, 'main', native_main), \
                patch.object(subprocess, 'Popen') as fake:
            continuation.main()
        self.assertEqual(fake.call_args.args[0], ['python', '-B', '-m', continuation.MODULE,
                                                'run', '--workers', '3'])


if __name__ == '__main__':
    unittest.main()
