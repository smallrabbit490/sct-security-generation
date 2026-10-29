"""验证工作台对真实分段、进程和修复派发的关键行为，不调用实验API。"""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from tools.cle_live_workbench import app


class WorkbenchTest(unittest.TestCase):
    def test_inventory_producer_and_reader_both_use_utf8(self):
        result = MagicMock(stdout='{"ProcessId":1,"CommandLine":"中文路径/python.exe"}')
        with patch.object(app.subprocess, 'run', return_value=result) as run:
            self.assertEqual(app.process_inventory()[0]['CommandLine'], '中文路径/python.exe')
        self.assertIn('[Console]::OutputEncoding', run.call_args.args[0][-1])
        self.assertEqual(run.call_args.kwargs['encoding'], 'utf-8')

    def test_windows(self):
        monday = dt.datetime(2026, 10, 26, tzinfo=app.SHANGHAI)
        for hour, expected in [(8, True), (9, False), (12, True), (14, False), (18, True)]:
            self.assertEqual(app.allowed(monday.replace(hour=hour)), expected)
        self.assertTrue(app.allowed(monday.replace(day=25, hour=10)))

    def test_missing_inventory_output_is_not_zero_workers(self):
        with patch.object(app.subprocess, 'run', return_value=MagicMock(stdout=None)):
            with self.assertRaisesRegex(ValueError, 'CIM_inventory_stdout_missing'):
                app.process_inventory()

    def test_process_parent_child_and_any_embedding_task(self):
        command = 'python -m configs.cle_weekly_embedding_recovery_20261027.resume run 999'
        values = [{'ProcessId': 1, 'ParentProcessId': 0, 'CommandLine': command},
                  {'ProcessId': 2, 'ParentProcessId': 1, 'CommandLine': command}]
        self.assertEqual(app.worker_processes(values), [
            {'pid': 2, 'package': 'FFS', 'workers': 3,
             'entry': 'configs.cle_weekly_embedding_recovery_20261027.resume run 999'}])
        self.assertEqual(app.process_package('python -m configs.cle_weekly_granularity_gate_20261027.evaluate run --workers 3'), 'FG_GATE')
        self.assertIsNone(app.process_package('python -m configs.cle_weekly_fs_20261027.evaluate check'))

    def test_live_process_overrides_stale_summary_and_dedup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / 'FFS/segment_001', root / 'FFS/segment_002'
            for segment in (a, b):
                (segment / 'task_rows').mkdir(parents=True)
                app.write_json(segment / 'summary.json', {'status': 'running', 'completed': 1})
                app.write_json(segment / 'task_rows/1.json', {'task_id': '1', 'cell_id': '1_r1_B0', 'final': {'joint': True}})
            app.write_json(root / 'FFS/execution_index.json', {'segments': [str(a), str(b)]})
            reserved = root / 'FG_LABELS/segment_001'
            reserved.mkdir(parents=True)
            app.write_json(reserved.parent / 'execution_index.json', {'segments': [str(reserved)]})
            c = app.Collector(root)
            with patch.object(app, 'allowed', return_value=True):
                status = c.collect([{'ProcessId': 2, 'ParentProcessId': 1,
                                     'CommandLine': 'python -m configs.cle_weekly_fs_20261027.evaluate run --workers 3'}])
                self.assertEqual(next(p for p in status['packages'] if p['key'] == 'FFS')['status'], 'running')
                self.assertEqual(len(status['rows']), 1)
                self.assertEqual(next(p for p in status['packages'] if p['key'] == 'FG_LABELS')['status'], 'not_started')
                self.assertFalse(any(x['kind'] == 'error' for x in app.incident_list(status)))
                dead = c.collect([])
                self.assertTrue(any(x['package'] == 'FFS' and x['kind'] == 'error' for x in app.incident_list(dead)))

    def test_real_credit_only(self):
        rows = [{'task_id': str(i), '_package': 'FQ_LEARN', '_time': i,
                 'q_credit_events': events, 'final': {'joint': True}} for i, events in enumerate([
                     [{'invariant_id': 'a', 'credited': True}, {'invariant_id': 'b', 'credited': False}],
                     [{'invariant_id': 'a', 'credited': True}, {'invariant_id': 'c', 'credited': True}]])]
        _, curve = app.summarize_rows(rows)
        self.assertEqual([p['coverage'] for p in curve], [1, 2])

    def test_registered_process_requires_pid_and_command_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app.write_json(root/'workbench_monitor/autonomy/registered_workers.json', [
                {'pid': 100, 'package': 'FX_GATE', 'workers': 4, 'command_marker': 'new_actual_entry.py'}])
            collector = app.Collector(root)
            wrong = collector.collect([{'ProcessId': 100, 'ParentProcessId': 1, 'CommandLine': 'unrelated.py'}])
            self.assertEqual(wrong['workers'], 0)
            right = collector.collect([{'ProcessId': 100, 'ParentProcessId': 1, 'CommandLine': 'python new_actual_entry.py run'}])
            self.assertEqual(right['workers'], 4)

    def test_registered_offline_replay_does_not_consume_paid_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root/'workbench_monitor/autonomy/registered_workers.json'
            entry = {'pid': 100, 'package': 'FQ_LEARN', 'workers': 0,
                     'command_marker': 'saved_feedback_replay.py'}
            app.write_json(path, [entry])
            processes = [{'ProcessId': 100, 'ParentProcessId': 1,
                          'CommandLine': 'python saved_feedback_replay.py run'}]
            collector = app.Collector(root, worker_reader=lambda _: [
                {'pid': 200, 'package': 'FQ_LEARN', 'workers': 1, 'entry': 'live_learning'}])
            status = collector.collect(processes)
            self.assertEqual(status['workers'], 1)
            self.assertEqual([p['pid'] for p in status['processes']], [200])
            for invalid in (-1, 5):
                app.write_json(path, [{**entry, 'workers': invalid}])
                with self.assertRaisesRegex(ValueError, 'registered_worker_count_outside_authorized_limit'):
                    collector.collect(processes)

    def test_activity_ignores_temporary_atomic_write_files(self):
        with tempfile.TemporaryDirectory() as temp:
            segment = Path(temp)
            wire = segment/'wire'
            wire.mkdir()
            (wire/'1.request.json').write_text('{}')
            (wire/'2.request.json.tmp').write_text('{}')
            self.assertEqual(app.latest_activity(segment)['file'], '1.request.json')

    def test_single_cli_dispatch_and_result(self):
        with tempfile.TemporaryDirectory() as temp:
            guardian = app.Guardian(temp)
            guardian.codex = 'codex.exe'
            process = MagicMock()
            process.pid, process.poll.return_value = 10, None
            event = {'id': 'test:once', 'kind': 'error', 'package': 'FFS'}
            with patch.object(app.subprocess, 'Popen', return_value=process) as popen:
                guardian.launch(event)
                guardian.tick({'packages': [], 'processes': [], 'allowed': True})
                self.assertEqual(popen.call_count, 1)
                self.assertIn('test:once', guardian.seen)
                prompt = (Path(guardian.current['folder']) / 'task.txt').read_text(encoding='utf-8')
                self.assertIn('累计预算', prompt)
                self.assertIn('不重复付费', prompt)
                self.assertEqual(popen.call_args.kwargs.get('shell', False), False)
                command = popen.call_args.args[0]
                self.assertEqual(command[command.index('--model') + 1], 'gpt-6.1-sol')
                self.assertIn('model_reasoning_effort="xhigh"', command)
                self.assertEqual(guardian.current['reasoning_effort'], 'xhigh')
            app.write_json(Path(guardian.current['folder']) / 'result.json',
                           {'status': 'resolved', 'summary': '已恢复', 'actions': [], 'remaining': []})
            process.poll.return_value, process.returncode = 0, 0
            guardian.enabled = False
            guardian.tick({'packages': [], 'processes': [], 'allowed': False})
            self.assertEqual(guardian.current['status'], 'finished')
            self.assertEqual(guardian.current['result']['summary'], '已恢复')

    def test_complete_pipeline_does_not_dispatch_extra_cli(self):
        snapshot = {'allowed': True, 'processes': [], 'packages': [
            {'key': 'SELFTEST_A', 'status': 'completed', 'completed': 3, 'segment': 'a'},
            {'key': 'SELFTEST_B', 'status': 'completed', 'completed': 2, 'segment': 'b'}]}
        self.assertEqual([e['kind'] for e in app.incident_list(snapshot)], ['stage_complete', 'stage_complete'])

    def test_error_never_falls_through_to_dispatch(self):
        snapshot = {'allowed': True, 'processes': [], 'packages': [
            {'key': 'SELFTEST_A', 'status': 'failed', 'completed': 1, 'segment': 'a'}]}
        self.assertEqual([e['kind'] for e in app.incident_list(snapshot)], ['error'])

    def test_capacity_wait_retries_same_incident_without_changing_model(self):
        with tempfile.TemporaryDirectory() as temp:
            g = app.Guardian(temp)
            event = {'id': 'error:SELFTEST_A:a:1', 'kind': 'error', 'package': 'SELFTEST_A'}
            g.state['pending_retry'] = {'incident': event, 'not_before': 100}
            g.seen.add(event['id'])
            snapshot = {'allowed': True, 'processes': [], 'packages': [
                {'key': 'SELFTEST_A', 'status': 'failed', 'completed': 1, 'segment': 'a'}]}
            with patch.object(app.time, 'time', return_value=99), patch.object(g, 'launch') as launch:
                g.tick(snapshot)
                launch.assert_not_called()
            with patch.object(app.time, 'time', return_value=101), patch.object(g, 'launch') as launch:
                g.tick(snapshot)
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0]['id'], event['id'])

    def test_isolated_cli_workdir_and_sandbox(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            g = app.Guardian(root, workdir=root, sandbox='workspace-write',
                             prompt_builder=lambda event, run: 'Only use this fixture directory.')
            g.codex = 'codex.exe'
            with patch.object(app.subprocess, 'Popen') as popen:
                popen.return_value.pid = 10
                g.launch({'id': 'isolated:test'})
                args = popen.call_args.args[0]
                self.assertEqual(args[args.index('-C') + 1], str(root))
                self.assertEqual(args[args.index('--sandbox') + 1], 'workspace-write')
                self.assertIn('--skip-git-repo-check', args)
                self.assertEqual(popen.call_args.kwargs['cwd'], root)


if __name__ == '__main__':
    unittest.main()
