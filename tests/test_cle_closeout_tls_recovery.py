"""TLS接续仅放行真实连接失败；已有成功响应、HTTP错误和重复进程均不重发。"""
from pathlib import Path
import unittest
from unittest.mock import patch

from configs.cle_weekly_closeout_20261101 import recover_tls as r
from methods.sct_trajectory.replay_journal import ReplayStop
from tools.cle_live_workbench.app import worker_processes


class TransportRecoveryTests(unittest.TestCase):
    def test_only_no_status_network_failure_is_allowed(self):
        record={'diagnostics':[{'category':'network_error'}]}
        good={'status':'transport_error','http_status':None,'error_type':'URLError'}
        self.assertIsNone(r.network_failure(record,[(Path('1'),good,b'')]))
        for status,raw in (({**good,'http_status':403},b''),
                           ({**good,'status':'response_read_error','http_status':200},b'partial'),
                           (good,b'complete response')):
            with self.assertRaises(ReplayStop):
                r.network_failure(record,[(Path('1'),status,raw)])
        with self.assertRaises(ReplayStop): r.network_failure(record,[])
        with self.assertRaises(ReplayStop): r.network_failure({'diagnostics':[{'category':'parse_error'}]},[(Path('1'),good,b'')])

    def test_duplicate_and_capacity_return_before_any_model_or_probe(self):
        with patch('tools.cle_live_workbench.app.process_inventory',return_value=[]), \
             patch('tools.cle_live_workbench.app.worker_processes',return_value=[{'package':'FQ_RETEST','workers':2}]), \
             patch('methods.sct_trajectory.provider_policy.ensure_model_call_allowed'), \
             patch.object(r,'probe') as probe:
            self.assertEqual(r.launch('q')['status'],'already_running')
            probe.assert_not_called()
        with patch('tools.cle_live_workbench.app.process_inventory',return_value=[]), \
             patch('tools.cle_live_workbench.app.worker_processes',return_value=[{'package':'OTHER','workers':3}]), \
             patch('methods.sct_trajectory.provider_policy.ensure_model_call_allowed'), \
             patch.object(r,'probe') as probe:
            with self.assertRaisesRegex(ReplayStop,'allocation_exceeded'): r.launch('q')
            probe.assert_not_called()

    def test_workbench_recognizes_new_parent_child_as_two_workers(self):
        cmd='python -m configs.cle_weekly_closeout_20261101.recover_tls run --kind gr --workers 2'
        rows=[{'ProcessId':1,'ParentProcessId':0,'CommandLine':cmd},
              {'ProcessId':2,'ParentProcessId':1,'CommandLine':cmd}]
        actual=worker_processes(rows)
        self.assertEqual(len(actual),1)
        self.assertEqual((actual[0]['package'],actual[0]['workers']),('FG_LABELS',2))


if __name__=='__main__': unittest.main()
