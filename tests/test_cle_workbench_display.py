"""修复后的展示须保留原生完成语义、物理用量与真实worker计数。"""
from pathlib import Path
import tempfile
import unittest

from tools.cle_live_workbench import app
from tools.cle_live_workbench.autonomy import AutonomousPlan


class WorkbenchDisplayTests(unittest.TestCase):
    def test_scope_and_omission_are_display_only(self):
        cross = {'key':'FX_GATE','planned':3576,'status':'not_started','summary':{}}
        p3 = {'key':'P3_EXTERNAL','planned':255,'status':'not_started','summary':{}}
        snapshot = {'packages':[cross,p3]}
        tasks = [
            {'package':'FX_GATE','kind':'run','expected':1788,'status':'waiting_dependency'},
            {'package':'FX_GATE','kind':'external','status':'blocked_external'},
            {'package':'P3_EXTERNAL','kind':'run','expected':255,'status':'completed',
             'display_status':'deferred','execution':'not_required_by_protocol'},
        ]
        app.task_display(snapshot, {'tasks':tasks})
        self.assertEqual(cross['display_planned'],1788)
        self.assertEqual(cross['planned'],3576)
        self.assertEqual(cross['status'],'not_started')
        self.assertEqual(p3['display_status'],'deferred')
        self.assertEqual(p3['display_planned'],0)
        self.assertEqual(p3['status'],'not_started')

    def test_all_learning_stages_counted_once_in_reported_usage(self):
        stages = {'K0':{'known_reported_tokens':10,'physical_HTTP':1,'unknown_or_inflight_HTTP':2},
                  'K1':{'known_reported_tokens':20,'physical_HTTP':3,'unknown_or_inflight_HTTP':1},
                  'K3':{'known_reported_tokens':3,'physical_HTTP':1,'unknown_or_inflight_HTTP':0}}
        snapshot = {'packages':[
            {'key':'FQ_LEARN','stages':stages,'summary':stages['K3']},
            {'key':'FFS','summary':{'known_reported_tokens':5,'physical_HTTP':2,'unknown_or_inflight_HTTP':4}},
        ]}
        app.task_display(snapshot, {'tasks':[]})
        self.assertEqual(snapshot['usage'],{'known_reported_tokens':38,'physical_HTTP':7,'unknown_or_inflight_HTTP':7})

    def test_excluded_reward_events_are_not_credited(self):
        rows = [{'_package':'FQ_LEARN','_time':1,'task_id':'1',
                 'q_credit_events':[{'invariant_id':'card1','credited':True},
                                    {'invariant_id':'card2','credited':False}]}]
        displayed,curve = app.summarize_rows(rows)
        self.assertEqual(displayed[0]['credits'],1)
        self.assertEqual(curve[0]['coverage'],1)

    def test_new_resume_segment_does_not_erase_saved_progress_or_usage_display(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            old,new=root/'FFS/one',root/'FFS/two'
            (old/'task_rows').mkdir(parents=True)
            new.mkdir(parents=True)
            app.write_json(old/'task_rows/1.json',{'task_id':'1','cell_id':'1_r1_BM'})
            app.write_json(old/'summary.json',{'completed':1,'known_reported_tokens':500,'physical_HTTP':4})
            app.write_json(new/'summary.json',{'status':'running','completed':0,'known_reported_tokens':0,'physical_HTTP':0})
            app.write_json(root/'FFS/execution_index.json',{'segments':[str(old),str(new)]})
            snapshot=app.Collector(root,packages={'FFS':('FFS',2980)}).collect([])
            package=snapshot['packages'][0]
            self.assertEqual(package['completed'],0)
            self.assertEqual(package['display_completed'],1)
            self.assertEqual(package['display_summary']['completed'],1)
            app.task_display(snapshot,{'tasks':[]})
            self.assertEqual(snapshot['usage']['known_reported_tokens'],500)

    def test_learning_display_stays_on_current_stage_instead_of_largest_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'K0';current=root/'K3'
            old.mkdir();current.mkdir()
            app.write_json(old/'summary.json',{'stage':'K0','completed':303})
            app.write_json(current/'summary.json',{'stage':'K3','completed':3})
            app.write_json(root/'execution_index.json',{'FQ_LEARN_K0':[str(old)],'FQ_LEARN_K3':[str(current)]})
            snapshot=app.Collector(root,packages={'FQ_LEARN':('Q',1122)}).collect([])
            self.assertEqual(snapshot['packages'][0]['display_summary']['stage'],'K3')
            self.assertEqual(snapshot['packages'][0]['display_summary']['completed'],3)

    def test_current_recovery_parent_child_is_one_worker_without_registry(self):
        for module,kind,package,workers in [
            ('cle_weekly_http403_recovery_20261028','q','FQ_LEARN',1),
            ('cle_weekly_http403_probe_refresh_20261028','ffs','FFS',3),
            ('cle_weekly_q_tls12_20261028','q','FQ_LEARN',1),
        ]:
            cmd=f'python -m configs.{module}.resume run --kind {kind}'
            processes=[{'ProcessId':1,'ParentProcessId':0,'CommandLine':cmd},
                       {'ProcessId':2,'ParentProcessId':1,'CommandLine':cmd}]
            result=app.worker_processes(processes)
            self.assertEqual(len(result),1)
            self.assertEqual((result[0]['pid'],result[0]['package'],result[0]['workers']),(2,package,workers))

    def test_launch_probe_and_check_do_not_occupy_api_slots(self):
        for module in ('cle_weekly_http403_recovery_20261028.resume',
                       'cle_weekly_http403_probe_refresh_20261028.resume',
                       'cle_weekly_q_tls12_20261028.resume',
                       'cle_weekly_fs_20261027.evaluate'):
            for action in ('launch','probe','check'):
                cmd=f'python -m configs.{module} {action} --kind ffs'
                self.assertEqual(app.worker_processes([
                    {'ProcessId':1,'ParentProcessId':0,'CommandLine':cmd}]),[])

    def test_omitted_task_unlocks_dependencies_but_does_not_count_as_done_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            app.write_json(root/'decision.json',{'status':'decided','action':'defer'})
            definition={'plan_id':'fixture','tasks':[
                {'id':'P3.external','title':'P3','kind':'run','package':'P3_EXTERNAL','depends':[],
                 'expected':255,'omit_when':{'path':'decision.json','field':'action','values':['defer']}},
                {'id':'after','title':'after','kind':'prepare','package':'NEXT','depends':['P3.external']},
            ]}
            manager=AutonomousPlan(root,definition)
            queue=manager.reconcile({'packages':[],'processes':[],'workers':0,'allowed':True})
            self.assertEqual(queue[0]['task_id'],'after')
            self.assertEqual(manager.view['counts']['completed'],1)
            self.assertEqual(manager.view['counts']['completed_verified'],0)
            self.assertEqual(manager.view['counts']['not_required'],1)
            self.assertEqual(manager.view['tasks'][0]['display_status'],'deferred')


if __name__=='__main__':
    unittest.main()
