"""未启动实验审查：活动定义不动、正式前缀不加量、契约修订可追溯；无模型请求。"""
import json
from pathlib import Path
import tempfile
import unittest

from configs.cle_experiment_review_20261028 import review as r
from methods.sct_trajectory.replay_journal import write_json
from tools.cle_live_workbench.autonomy import AutonomousPlan


class ReviewTests(unittest.TestCase):
    def test_only_nine_unstarted_runs_changed_and_graph_remains_valid(self):
        p=json.loads((r.ROOT/'tools/cle_live_workbench/autonomy_plan.json').read_text(encoding='utf-8-sig'))
        # 使用审查前计划，不把运行现场是否已经安装当作测试前提。
        before=r.CONTROL/'original_autonomy_plan.json'
        if before.exists():p=r.scope.read(before)
        new=r.update_plan(p)
        old_by={t['id']:t for t in p['tasks']}
        new_by={t['id']:t for t in new['tasks']}
        changed={k for k in old_by if old_by[k]!=new_by[k]}
        self.assertEqual(changed,{v['task'] for v in r.PROBES})
        for key in ('Q.run','FS.run','Q.K0.analysis','Q.K1.analysis','BUILD.prepare','CROSS.prepare'):
            self.assertEqual(old_by[key],new_by[key])
        self.assertEqual(new_by['FR.run']['depends'],['GR.labels.analysis','FS.analysis'])
        self.assertNotIn('order_after',new_by['FR.run'])
        with tempfile.TemporaryDirectory() as temp:AutonomousPlan(temp,new)
        self.assertEqual(r.update_plan(new),new)

    def test_prefixes_are_part_of_formal_budget_and_not_performance_gates(self):
        for p in r.PROBES:
            if p['units'] is not None:
                self.assertLess(p['units'],p['total'])
                self.assertEqual(p['tasks']*p['conditions']*p['repeats'],p['units'])
            self.assertIn('低Joint不阻止',r.prefix_note(p))
        cross=next(p for p in r.PROBES if p['experiment']=='C10')
        self.assertEqual(cross['new_C41_units']+cross['FFS_reused_units'],72)

    def test_retest_migration_preserves_schedule_and_old_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);control=run/'review';inputs=run/'FQ_RETEST/inputs'
            old={str(i):{'index':i,'family_id':str(i),'prompt':'old'} for i in range(273)}
            new={str(i):{'index':i,'family_id':str(i),'prompt':'new'} for i in range(273)}
            write_json(inputs/'tasks.json',old)
            write_json(inputs/'schedule.json',[{'cell_id':'one'}])
            write_json(inputs/'protocol.json',{'planned_P7':1416,'budget_proposed':{'limit':123}})
            write_json(run/'FG_LABELS/inputs_contract_v2/tasks.json',new)
            write_json(run/'FG_LABELS/preflight_contract_v2/summary.json',{'reference_and_name_checks_passed':273})
            schedule=(inputs/'schedule.json').read_bytes()
            r.migrate_retest(run,control)
            self.assertEqual(r.scope.read(inputs/'tasks.json'),new)
            self.assertEqual(r.scope.read(control/'original_retest_inputs/tasks.json'),old)
            self.assertEqual(schedule,(inputs/'schedule.json').read_bytes())
            self.assertEqual(r.scope.read(inputs/'protocol.json')['budget_proposed'],{'limit':123})
            write_json(run/'FQ_RETEST/execution_index.json',{'segments':['existing']})
            with self.assertRaisesRegex(ValueError,'already_has_segments'):r.migrate_retest(run,control)

    def test_probe_selection_stays_in_frozen_pools(self):
        m=r.probe_manifest()
        selected=r.scope.read(r.RUN/'scope_reduction_20261028/selection.json')
        self.assertFalse(m['selection_uses_model_results'])
        for p in m['probes']:
            self.assertEqual(p['status'],'planned_not_executed')
            self.assertEqual(p['extra_paid_units'],0)
            self.assertEqual(len(p['task_ids']),len(set(p['task_ids'])))
            if p['experiment']=='C02':self.assertLessEqual(set(p['task_ids']),set(selected['Q_intermediate_54']))
            if p['experiment']=='C04':self.assertLessEqual(set(p['task_ids']),set(selected['GR_first_82']))


if __name__=='__main__':unittest.main()
