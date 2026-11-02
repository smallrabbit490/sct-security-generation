"""工作台只读采样的回归：新入口、续段、真实退出及阶段切换；不发模型请求。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.cle_live_workbench import app
from tools.cle_live_workbench.current_view import apply_current_view, batch_detail


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        app.write_json(self.root/'supervised_remaining_20261029.json',
                       {'execution_owner':'current_chat', 'status':'two_registered_batches_resumed'})
        self.q = self.root/'probe_relay_20261028/Q.retest/segment_003'
        self.gr = self.root/'FG_LABELS/segment_002'
        for segment, planned in ((self.q,540),(self.gr,820)):
            app.write_json(segment.parent/'execution_index.json', {'segments':[str(segment)]})
            self.save(segment,1,planned)
        self.collector = app.Collector(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def save(self,segment,count,planned,status='running'):
        app.write_json(segment/'summary.json',dict(completed=count, planned=planned,status=status,
            updated_utc='2026-11-01T03:00:00+00:00', arms={'one':dict(completed=count,measured=count,joint=1)},
            known_reported_tokens=count*100,physical_HTTP=count,unknown_or_inflight_HTTP=0))
        app.write_json(segment/'state.json',dict(status=status,completed_P7=count))
        app.write_json(segment/f'task_rows/{count}.json',dict(cell_id=str(count),task_id=str(count),final={'joint':True}))

    def processes(self):
        rows=[]
        for parent,kind in ((100,'q'),(200,'gr')):
            command=f'python -m configs.cle_weekly_closeout_20261101.resume run --kind {kind} --workers 2'
            rows.extend([dict(ProcessId=parent,ParentProcessId=0,CommandLine=command),
                         dict(ProcessId=parent+1,ParentProcessId=parent,CommandLine=command)])
        return rows

    def collect(self,processes):
        with patch.object(app,'allowed',return_value=True):
            snapshot=self.collector.collect(processes)
        tasks={'tasks':[dict(id='Q.retest.probe',status='paused'),dict(id='GR.labels',status='paused')]}
        snapshot['autonomy']=apply_current_view(snapshot,tasks,self.root,app.read_json)
        return snapshot,{p['key']:p for p in snapshot['packages']}

    def test_new_entries_parent_child_two_plus_two_and_no_launch_count(self):
        s,pkgs=self.collect(self.processes())
        self.assertEqual(s['workers'],4)
        self.assertEqual(len(s['processes']),2)
        self.assertEqual(pkgs['FQ_RETEST']['display_planned'],540)
        self.assertEqual(pkgs['FG_LABELS']['display_planned'],820)
        self.assertEqual(pkgs['FQ_RETEST']['display_status'],'running')
        self.assertEqual(s['autonomy']['tasks'][0]['status'],'running')
        cmd=self.processes()[0]['CommandLine'].replace(' run ',' launch ')
        self.assertIsNone(app.process_package(cmd))

    def test_new_saved_row_and_resume_segment_appear_without_restart(self):
        first,_=self.collect(self.processes())
        self.save(self.q,2,540)
        newer=self.q.parent/'segment_004'
        self.save(newer,3,540)
        app.write_json(self.q.parent/'execution_index.json', {'segments':[str(self.q),str(newer)]})
        second,p=self.collect(self.processes())
        self.assertEqual(p['FQ_RETEST']['display_completed'],3)
        self.assertEqual(p['FQ_RETEST']['segment'],str(newer))
        self.assertGreater(len(second['rows']),len(first['rows']))
        self.assertEqual(p['FQ_RETEST']['usage_summary']['physical_HTTP'],3)

    def test_real_failure_is_not_paused_or_running_and_keeps_saved_results(self):
        self.save(self.q,73,540,'needs_technical_recovery')
        s,p=self.collect([])
        self.assertEqual(s['workers'],0)
        self.assertEqual(p['FQ_RETEST']['display_status'],'needs_technical_recovery')
        self.assertEqual(p['FQ_RETEST']['display_completed'],73)
        self.assertEqual(p['FG_LABELS']['display_status'],'interrupted')

    def test_analysis_does_not_occupy_model_slots_and_old_statistics_not_current(self):
        self.save(self.q,540,540,'completed')
        app.write_json(self.q.parent/'analysis_20261101/summary.json',{'status':'partial','completed':16})
        s,p=self.collect(self.processes())
        self.assertEqual(s['workers'],2)
        self.assertEqual(p['FQ_RETEST']['display_status'],'postprocessing')
        self.assertFalse(p['FQ_RETEST']['workflow']['statistics_current'])
        self.assertEqual(p['FQ_RETEST']['workflow']['generation'],'completed')
        s,p=self.collect([])
        self.assertEqual(p['FQ_RETEST']['display_status'],'awaiting_analysis')

    def test_budget_usage_overrides_stale_summary_once_and_request_is_allowlisted(self):
        app.write_json(self.q/'budget.json',dict(known_reported_tokens=200,transport_attempts_including_prior=4,
            entries=[{'status':'reported'},{'status':'failed_unknown'}],cap_HTTP=100,cap_tokens=10000))
        app.write_json(self.q/'journals/x/requests/1.json',dict(prompt='not for UI',settings={'private':'not for UI'},
            identity='1',status='failed_or_unresolved',selector=True,started_utc='2026-11-01T03:00:00Z'))
        s,p=self.collect([])
        self.assertEqual(p['FQ_RETEST']['usage_summary']['known_reported_tokens'],200)
        self.assertEqual(p['FQ_RETEST']['usage_summary']['unknown_or_inflight_HTTP'],1)
        self.assertEqual(s['usage']['physical_HTTP'],5)
        self.assertNotIn('prompt',p['FQ_RETEST']['request'])
        self.assertNotIn('settings',p['FQ_RETEST']['request'])
        self.assertEqual(p['FQ_RETEST']['request']['cell_id'],'x')

    def test_collector_retains_lightweight_rows_and_detail_source(self):
        path=self.q/'task_rows/1.json'
        app.write_json(path,dict(cell_id='1',task_id='1',
            final={'joint':True,'code':'large code'}, attempts=[{'code':'large code'}],
            mechanism=[{'selected':['c1'],'adopted':['c1'],'full_candidates':'large prompt'}]))
        snapshot,_=self.collect([])
        compact=self.collector.rows[('FQ_RETEST','1')]
        self.assertNotIn('attempts',compact)
        self.assertNotIn('code',compact['final'])
        self.assertNotIn('full_candidates',compact['mechanism'][0])
        self.assertEqual(self.collector.row_paths[('FQ_RETEST','1')],path)
        self.assertEqual(next(r for r in snapshot['rows'] if r['package']=='FQ_RETEST')['selected'],['c1'])


if __name__=='__main__': unittest.main()
