"""验证一次性授权精确到期；不调用模型、不改已有实验进程。"""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.cle_live_workbench import time_policy
from methods.sct_trajectory import provider_policy


class TimeOverrideTests(unittest.TestCase):
    def test_request_boundary_and_midnight_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp)/'authorization.json'
            record.write_text(json.dumps({'enabled': True,
                'starts_at': '2026-10-28T08:36:00+08:00',
                'expires_at': '2026-10-29T00:00:00+08:00'}), encoding='utf-8')
            original = provider_policy.ensure_model_call_allowed
            with patch.object(provider_policy, 'ensure_model_call_allowed', original):
                time_policy.install(record)
                guard = provider_policy.ensure_model_call_allowed
                for moment in ['2026-10-28T09:00:00+08:00', '2026-10-28T14:00:00+08:00',
                               '2026-10-28T23:59:59+08:00']:
                    guard(provider_policy.CURRENT_MODEL, now=dt.datetime.fromisoformat(moment))
                self.assertFalse(time_policy.override_active(
                    dt.datetime.fromisoformat('2026-10-29T00:00:00+08:00'), record))
                with self.assertRaises(provider_policy.ModelTimeWindowError):
                    guard(provider_policy.CURRENT_MODEL,
                          now=dt.datetime.fromisoformat('2026-10-29T09:00:00+08:00'))

    def test_cli_environment_preserves_existing_entries(self):
        with patch.object(time_policy, 'RECORD') as record:
            record.is_file.return_value = True
            env = time_policy.child_environment({'PYTHONPATH': 'existing', 'TASK_VALUE': 'kept'})
        self.assertEqual(env['TASK_VALUE'], 'kept')
        self.assertTrue(env['PYTHONPATH'].endswith('existing'))
        self.assertIn('runtime_bootstrap', env['PYTHONPATH'])


if __name__ == '__main__':
    unittest.main()
