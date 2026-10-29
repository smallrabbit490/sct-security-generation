"""v08执行接线和阶段交付的封网验证；不启动正式实验。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configs.cle_scientific_review_20261028.execution_binding import bind
from tools import build_cle_horizontal_ideas as diagrams
from tools.cle_live_workbench import app, delivery
from tools.cle_live_workbench.autonomy import AutonomousPlan


class ExecutionBindingTests(unittest.TestCase):
    def test_binding_changes_only_future_tasks(self):
        plan = app.read_json(Path(app.__file__).with_name('autonomy_plan.json'))
        new = bind(plan)
        before = {t['id']:t for t in plan['tasks']}
        after = {t['id']:t for t in new['tasks']}
        for identity in ('Q.run','FS.run','Q.K0.analysis','Q.K1.analysis','Q.K2.analysis',
                         'BUILD.prepare','CROSS.prepare'):
            self.assertEqual(before[identity],after[identity])
        self.assertEqual(new,bind(new))
        self.assertEqual(after['Q.retest']['expected'],1416)
        self.assertEqual(after['GR.labels']['expected'],820)
        self.assertEqual(after['FR.run']['expected'],57)
        self.assertEqual(after['CROSS.v41']['expected'],1788)
        self.assertIn('cle_weekly_cross_readiness_20261028',after['CROSS.v41']['commands'][0])
        for task in new['tasks']:
            if task.get('narrative'):
                self.assertTrue(task['narrative']['receipt'].endswith('/receipt.json'))

    def test_cross_worker_limit(self):
        plan = {'plan_id':'test','tasks':[{'id':'cross','title':'cross','kind':'run',
            'package':'FX_GATE','depends':[],'expected':1,'max_workers':3}]}
        with tempfile.TemporaryDirectory() as temp:
            manager = AutonomousPlan(temp,plan)
            self.assertEqual(manager.packet(plan['tasks'][0],{'workers':0})['work_item']['allocated_workers'],3)

    def test_stage_text_updates_are_scoped_to_idea(self):
        specs=diagrams.specifications()
        items={k:{} for k in diagrams.CARD_TEXT}
        node=next(diagrams.walk(specs[3]['root']))
        original=specs[0]['root'].title
        diagrams.apply_updates(specs,items,{'4':{'answer':'已取得本批比较结果',
            'tasks':{node.key:['实际阶段','实际结果','下一步']},
            'cards':{'B02':['五条件对照','本批实际Joint差','2980次']}}})
        self.assertEqual(specs[0]['root'].title,original)
        self.assertEqual(specs[3]['answer'],'已取得本批比较结果')
        self.assertEqual(items['B02']['meaning'],'本批实际Joint差')
        with self.assertRaises(ValueError):
            diagrams.apply_updates(specs,items,{'4':{'answer':'错误跨线','cards':{'C03':['x','y','z']}}})

    def fixture(self, root):
        task={'id':'analysis','title':'实验分析','kind':'analysis','package':'A','depends':[],
              'expected':1,'analysis_dir':'A/analysis','replay':'A/replay.json',
              'narrative':{'source':'docs/story.md','sections':['idea04'],
                           'receipt':'workbench_monitor/autonomy/deliveries/analysis/receipt.json'}}
        plan={'plan_id':'test','tasks':[task,{'id':'next','title':'next','kind':'run',
               'package':'B','depends':['analysis'],'expected':1}]}
        app.write_json(root/'A/analysis/summary.json',{'status':'completed','completed':1})
        app.write_json(root/'A/replay.json',{'status':'passed'})
        app.write_json(root/'A/analysis/case_review_queue.json',[])
        (root/'A/analysis/analysis.md').write_text('实际分析',encoding='utf-8')
        snap={'time':'2026-10-28T18:00:00+08:00','packages':[], 'processes':[],
              'workers':0,'allowed':True}
        return plan, task, snap

    def test_native_result_without_delivery_does_not_release_next(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); plan,task,snap=self.fixture(root)
            manager=AutonomousPlan(root,plan)
            self.assertTrue(manager.native_evidence_done(task,snap))
            self.assertFalse(manager.native_done(task,snap))
            self.assertEqual(manager.reconcile(snap)[0]['task_id'],'analysis')
            evidence=root/'A/analysis/analysis.md'
            receipt={'task_id':'analysis','status':'completed','sections':['idea04'],
                     'experiment_API_calls':0,'evidence':[str(evidence)]}
            app.write_json(root/task['narrative']['receipt'],receipt)
            self.assertEqual(manager.reconcile(snap)[0]['task_id'],'next')
            evidence.unlink()
            self.assertFalse(manager.native_done(task,snap))

    def test_omitted_branch_does_not_require_fake_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); plan,task,snap=self.fixture(root)
            task['omit_when']={'path':'decision.json','field':'action','values':['stop']}
            app.write_json(root/'decision.json',{'status':'decided','action':'stop'})
            manager=AutonomousPlan(root,plan)
            self.assertEqual(manager.reconcile(snap)[0]['task_id'],'next')

    def test_publish_writes_story_and_related_diagrams_then_unlocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,task,snap=self.fixture(root)
            manager=AutonomousPlan(root,plan)
            (root/'docs').mkdir()
            story=root/'docs/story.md'
            story.write_text('<a id="idea04"></a>\n## 原叙事\n\n历史结果。\n<a id="idea05"></a>\n其他思路。',encoding='utf-8')
            section={k:'实际依据与判断' for k in delivery.FIELDS}
            section['diagram']={'answer':'本批实际结论','cards':{'B02':['完整比较','实际差值','2980次']}}
            draft=root/'draft.json'
            app.write_json(draft,{'task_id':'analysis','evidence':['A/analysis/summary.json'],
                                  'sections':{'idea04':section}})
            out=root/'docs/diagrams';out.mkdir()
            stem=diagrams.specifications()[3]['stem']
            def render(snapshot,only,updates):
                self.assertEqual(only,[4])
                for suffix in ('.svg','.png'):
                    (out/(stem+suffix)).write_bytes(b'isolated renderer fixture')
            with patch.object(app,'ROOT',root), patch.object(delivery,'AutonomousPlan',return_value=manager), \
                 patch.object(app.Collector,'collect',return_value=snap), \
                 patch.object(app,'process_inventory',return_value=[]), \
                 patch.object(diagrams,'OUT',out), patch.object(diagrams,'main',side_effect=render) as renderer:
                result=delivery.publish('analysis',draft,root)
                self.assertTrue(manager.native_done(task,snap))
                self.assertEqual(result['experiment_API_calls'],0)
                self.assertIn('历史结果',story.read_text(encoding='utf-8'))
                self.assertIn('实测结果',story.read_text(encoding='utf-8'))
                self.assertEqual(story.read_text(encoding='utf-8').count('其他思路'),1)
                self.assertTrue(all(Path(p).is_file() for p in result['evidence']))
                delivery.publish('analysis',draft,root)
                self.assertEqual(renderer.call_count,1)

    def test_publish_cannot_rewrite_story_before_native_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,task,snap=self.fixture(root)
            manager=AutonomousPlan(root,plan)
            (root/'A/replay.json').unlink()
            with patch.object(delivery,'AutonomousPlan',return_value=manager), \
                 patch.object(app.Collector,'collect',return_value=snap), \
                 patch.object(app,'process_inventory',return_value=[]):
                with self.assertRaisesRegex(ValueError,'not_complete'):
                    delivery.publish('analysis',root/'missing.json',root)


if __name__=='__main__':
    unittest.main()
