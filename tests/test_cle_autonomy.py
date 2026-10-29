"""任务编排的依赖、完成证据、继续推进和并发检查；不调用模型。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.cle_live_workbench import app
from tools.cle_live_workbench.autonomy import AutonomousPlan


def plan(tasks):
    return {'plan_id': 'isolated-autonomy-check', 'tasks': tasks}


def task(identity, kind='run', package='A', depends=None, **extra):
    return {'id': identity, 'title': identity, 'kind': kind, 'package': package,
            'depends': depends or [], 'priority': 10, 'expected': 1, 'slots': 'available', **extra}


def snapshot(packages=None, workers=None, allowed=True):
    workers = workers or []
    return {'packages': packages or [], 'processes': workers, 'workers': sum(w['workers'] for w in workers),
            'allowed': allowed}


def package(key, completed=0, status='not_started'):
    return {'key': key, 'completed': completed, 'status': status, 'segment': key, 'stages': {}}


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_execution_analysis_then_next_stage(self):
        tasks = [task('runA'), task('analysisA', 'analysis', depends=['runA'], expected=1,
                    analysis_dir='A/analysis', replay='A/replay.json'),
                 task('runB', package='B', depends=['analysisA'])]
        manager = AutonomousPlan(self.root, plan(tasks))
        current = snapshot([package('A', 1, 'completed'), package('B')])
        queue = manager.reconcile(current)
        self.assertEqual(queue[0]['task_id'], 'analysisA')
        app.write_json(self.root/'A/analysis/summary.json', {'status': 'completed', 'completed': 1})
        app.write_json(self.root/'A/replay.json', {'status': 'passed'})
        (self.root/'A/analysis/analysis.md').write_text('actual analysis')
        app.write_json(self.root/'A/analysis/case_review_queue.json', [{'task_id': '1'}])
        self.assertEqual(manager.reconcile(current)[0]['task_id'], 'analysisA')
        (self.root/'row.json').write_text('{}')
        app.write_json(self.root/'A/analysis/agent_case_review.json', {'status': 'completed', 'cases': [
            {'task_id': '1', 'analysis': 'read code and validation', 'evidence': ['row.json']}]})
        self.assertEqual(manager.reconcile(current)[0]['task_id'], 'runB')

    def test_cli_says_resolved_does_not_complete_missing_work(self):
        manager = AutonomousPlan(self.root, plan([task('runA')]))
        current = {'job_id': 'j1', 'status': 'finished', 'incident': {'task_id': 'runA'},
                   'result': {'status': 'resolved'}}
        with patch('tools.cle_live_workbench.autonomy.time.time', return_value=100):
            manager.reconcile(snapshot([package('A')]), current)
        self.assertNotEqual(manager.view['tasks'][0]['status'], 'completed')
        with patch('tools.cle_live_workbench.autonomy.time.time', return_value=121):
            queue = manager.reconcile(snapshot([package('A')]), current)
        self.assertEqual(queue[0]['work_item']['attempt'], 1)

    def test_active_package_never_launches_second_worker(self):
        manager = AutonomousPlan(self.root, plan([task('runA')]))
        queue = manager.reconcile(snapshot([package('A')], [{'pid': 1, 'package': 'A', 'workers': 3}]))
        self.assertEqual(queue, [])
        self.assertEqual(manager.view['tasks'][0]['status'], 'running')

    def test_active_preparation_cli_is_running_not_ready(self):
        manager = AutonomousPlan(self.root, plan([task('prepare', 'prepare')]))
        current = {'status': 'running', 'incident': {'task_id': 'prepare'}}
        self.assertEqual(manager.reconcile(snapshot(), current), [])
        self.assertEqual(manager.view['tasks'][0]['status'], 'running')

    def test_window_blocks_paid_not_offline_preparation(self):
        manager = AutonomousPlan(self.root, plan([task('runA'), task('prepare', 'prepare', package='C')]))
        queue = manager.reconcile(snapshot([package('A')], allowed=False))
        self.assertEqual([e['task_id'] for e in queue], ['prepare'])
        self.assertEqual(manager.view['tasks'][0]['status'], 'waiting_window')

    def test_learning_one_plus_evaluation_three(self):
        manager = AutonomousPlan(self.root, plan([task('runA')]))
        queue = manager.reconcile(snapshot([package('A')], [{'pid': 1, 'package': 'FQ_LEARN', 'workers': 1}]))
        self.assertEqual(queue[0]['work_item']['allocated_workers'], 3)
        self.assertEqual(manager.reconcile(snapshot([package('A')], [
            {'pid': 1, 'package': 'FQ_LEARN', 'workers': 1}, {'pid': 2, 'package': 'B', 'workers': 3}])), [])

    def test_external_block_only_blocks_related_tasks(self):
        tasks = [task('image', 'prepare', requires_image=True),
                 task('dependent', depends=['image']), task('independent', 'prepare', package='C')]
        manager = AutonomousPlan(self.root, plan(tasks))
        with patch.object(manager, 'image_ready', return_value=False):
            queue = manager.reconcile(snapshot([package('A')]))
        self.assertEqual([e['task_id'] for e in queue], ['independent'])
        indexed = {v['id']: v for v in manager.view['tasks']}
        self.assertEqual(indexed['image']['status'], 'blocked_external')
        self.assertEqual(indexed['dependent']['status'], 'blocked_external')

    def test_error_cannot_fall_through_to_normal_launch(self):
        manager = AutonomousPlan(self.root, plan([task('runA')]))
        queue = manager.reconcile(snapshot([package('A', 0, 'failed')]))
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['work_item']['operation'], 'repair')

    def test_forbidden_window_does_not_repeat_paid_recovery_jobs(self):
        manager = AutonomousPlan(self.root, plan([task('runA'), task('offline', 'prepare', package='B')]))
        queue = manager.reconcile(snapshot([package('A', 0, 'failed')], allowed=False))
        self.assertEqual([e['task_id'] for e in queue], ['offline'])

    def test_restart_preserves_finished_job_consumption(self):
        definition = plan([task('runA')])
        current = {'job_id': 'j1', 'status': 'finished', 'incident': {'task_id': 'runA'}, 'result': {'status': 'resolved'}}
        AutonomousPlan(self.root, definition).reconcile(snapshot([package('A')]), current)
        restarted = AutonomousPlan(self.root, definition)
        restarted.reconcile(snapshot([package('A')]), current)
        self.assertEqual(restarted.state['tasks']['runA']['attempts'], 1)

    def test_topological_order_and_cycle(self):
        manager = AutonomousPlan(self.root, plan([task('second', depends=['first']), task('first')]))
        self.assertEqual([t['id'] for t in manager.tasks], ['first', 'second'])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            AutonomousPlan(self.root, plan([task('a', depends=['b']), task('b', depends=['a'])]))

    def test_finished_job_replaced_in_same_tick_is_consumed_from_history(self):
        manager = AutonomousPlan(self.root, plan([task('runA'), task('runB', package='B')]))
        finished = {'job_id': 'a1', 'status': 'finished', 'incident': {'task_id': 'runA'},
                    'result': {'status': 'resolved'}}
        next_job = {'job_id': 'b1', 'status': 'running', 'incident': {'task_id': 'runB'}}
        current = snapshot([package('A', 0, 'failed')],
                           [{'pid': 1, 'package': 'FQ_LEARN', 'workers': 1}])
        with patch('tools.cle_live_workbench.autonomy.time.time', return_value=100):
            manager.reconcile(current, next_job, history=[finished])
        with patch('tools.cle_live_workbench.autonomy.time.time', return_value=121):
            queue = manager.reconcile(current, next_job, history=[finished])
        self.assertEqual(manager.state['tasks']['runA']['attempts'], 1)
        self.assertEqual(queue[0]['id'], 'autonomy:runA:1:repair')
        self.assertEqual(queue[0]['work_item']['allocated_workers'], 3)
        self.assertEqual(manager.state['consumed_jobs'], ['a1'])

    def test_native_custom_counts_cannot_be_double_counted(self):
        entry = task('customrun', custom=True, expected=2)
        manager = AutonomousPlan(self.root, plan([entry]))
        app.write_json(self.root/'native.json', {'status': 'completed', 'completed': 1})
        app.write_json(manager.receipt_path(entry), {'status': 'completed', 'evidence': ['native.json'],
            'native_counters': [{'path': 'native.json', 'field': 'completed'}]*2})
        self.assertFalse(manager.native_done(entry, snapshot()))

    def test_external_dependency_arrival_automatically_unlocks(self):
        manager = AutonomousPlan(self.root, plan([task('prepare', 'prepare', requires_image=True)]))
        with patch.object(manager, 'image_ready', return_value=False):
            self.assertEqual(manager.reconcile(snapshot()), [])
        with patch.object(manager, 'image_ready', return_value=True):
            self.assertEqual(manager.reconcile(snapshot())[0]['task_id'], 'prepare')


if __name__ == '__main__':
    unittest.main()
