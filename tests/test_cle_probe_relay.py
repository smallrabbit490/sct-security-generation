"""探针接力只改变调度，不启动真实模型或实验进程。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.cle_live_workbench.autonomy import AutonomousPlan


def node(identity, package, scope, **extra):
    return dict(id=identity, title=identity, kind='run', package=package,
                expected=100, depends=[], priority=10, execution_scope=scope, **extra)


class ProbeRelayTests(unittest.TestCase):
    def test_skip_full_continue_probe_and_started_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan={'plan_id':'test','dispatch_policy':{'mode':'probe_relay','continue_started':['Q.run']},
                  'tasks':[node('full','F','full'),node('small','S','probe_batch',order_after='full'),node('Q.run','Q','full')]}
            manager=AutonomousPlan(Path(tmp),plan)
            snapshot={'packages':[],'processes':[],'workers':0,'allowed':True}
            queue=manager.reconcile(snapshot)
            self.assertEqual({q['task_id'] for q in queue},{'small','Q.run'})
            states={t['id']:t['status'] for t in manager.view['tasks']}
            self.assertEqual(states['full'],'deferred_full')
            self.assertNotEqual(states['full'],'completed')

    def test_scientific_dependency_not_faked(self):
        with tempfile.TemporaryDirectory() as tmp:
            later=node('dependent','D','probe_batch');later['depends']=['full']
            plan={'plan_id':'test','dispatch_policy':{'mode':'probe_relay'},'tasks':[node('full','F','full'),later]}
            m=AutonomousPlan(Path(tmp),plan)
            self.assertEqual(m.reconcile({'packages':[],'processes':[],'workers':0,'allowed':True}),[])
            self.assertEqual(m.view['tasks'][1]['status'],'waiting_dependency')

    def test_error_repair_cannot_bypass_full_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=AutonomousPlan(Path(tmp),{'plan_id':'test','dispatch_policy':{'mode':'probe_relay'},'tasks':[node('full','F','full')]})
            with patch('tools.cle_live_workbench.app.incident_list',return_value=[{'kind':'error','package':'F'}]):
                self.assertEqual(m.reconcile({'packages':[],'processes':[],'workers':0,'allowed':True}),[])

    def test_installed_plan_keeps_started_and_probe_limits(self):
        import json
        root=Path(__file__).resolve().parents[1]
        plan=json.loads((root/'tools/cle_live_workbench/autonomy_plan.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            m=AutonomousPlan(Path(tmp),plan)
            by=m.definitions
            self.assertFalse(m.full_deferred(by['Q.run']))
            self.assertFalse(m.full_deferred(by['FS.run']))
            self.assertTrue(m.full_deferred(by['Q.retest']))
            self.assertEqual(by['Q.retest.probe']['expected'],540)
            self.assertEqual(len(by['Q.retest.probe']['probe_scope']['task_ids']),54)
            self.assertEqual(by['GR.labels']['expected'],820)
            self.assertEqual(by['FR.run']['expected'],57)
            self.assertTrue(all(not t['commands'] for t in m.tasks if t['kind']=='probe'))


if __name__=='__main__':unittest.main()
