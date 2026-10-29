"""减量名单、非矩形配对、分批扩大和工作台接续；全部封网。"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_reduced_20261028 import scope, retest, adaptive, retest_analysis
from configs.cle_weekly_reduced_20261028 import granularity
from configs.cle_weekly_reduced_20261028 import retrieval_execute
from methods.sct_trajectory.replay_journal import write_json
from tools.cle_live_workbench import app
from tools.cle_live_workbench.autonomy import AutonomousPlan
import test_cle_weekly_frozen_retest as fixture
import test_cle_weekly_granularity as gran_fixture
import test_cle_weekly_retrieval_execution as retrieval_fixture


class ReducedGridTests(fixture.FrozenRetestTest):
    """复用原生P7集成夹具，新增不等规模条件的执行、恢复和回放。"""
    def setUp(self):
        self.module_patch=patch.object(fixture,'m',retest)
        self.module_patch.start(); self.addCleanup(self.module_patch.stop)
        super().setUp()

    # 原测试也在独立减量入口运行，验证P7、反馈边界与恢复行为一致。
    def test_nonrectangular_primary_full_and_diagnostic_subset(self):
        cells=[c for c in self.cells if c['task_id']=='1' or c['condition'] in ('Q1','Q2_K3')]
        write_json(self.inputs/'schedule.json',cells)
        protocol=retest.read(self.inputs/'protocol.json'); protocol['planned_P7']=len(cells)
        write_json(self.inputs/'protocol.json',protocol)
        with self.guards():
            study=retest.FrozenRetest(); study.io.physical_open=self.service
            self.assertEqual(study.execute()['completed'],14)
            checks=[retest.read(p) for p in (study.out/'common_candidates').glob('*.json')]
            self.assertEqual(sorted(c['expected_conditions'] for c in checks),[2,2,5,5])
            self.assertTrue(all(c['status']=='passed' for c in checks))
            calls=len(self.http)
            replay=retest.FrozenRetest([study.out],offline=True,destination=self.root/'zero_api')
            replay.execute(); self.assertEqual(len(self.http),calls)
            resumed=retest.FrozenRetest([study.out],destination=self.root/'resumed')
            resumed.io.physical_open=self.service
            self.assertEqual(resumed.execute()['completed'],14)
            self.assertEqual(len(self.http),calls)


class ReducedGranularityTests(gran_fixture.FrozenGranularityTest):
    def setUp(self):
        for module,key,value in [(fixture,'m',retest),(gran_fixture,'base',retest),(gran_fixture,'fg',granularity)]:
            context=patch.object(module,key,value);context.start();self.addCleanup(context.stop)
        super().setUp()

    def guards(self):
        # 旧测试文件通过tests包再次导入夹具，显式使用当前模块避免补丁落在另一个实例。
        stack=fixture.FrozenRetestTest.guards(self)
        stack.enter_context(patch.object(granularity,'old_binding_catalog',return_value={}))
        self.assertEqual(retest.RUN,self.root)
        return stack


class ReducedRetrievalTests(retrieval_fixture.RetrievalExecutionTest):
    def setUp(self):
        context=patch.object(retrieval_fixture,'m',retrieval_execute)
        context.start();self.addCleanup(context.stop)
        super().setUp()

    def test_budget_is_finite_and_covers_registered_extra_pairs(self):
        with self.guards():
            self.inputs(); protocol=retrieval_execute.prepare()
            self.assertEqual(protocol['pair_limit'],10767)
            self.assertEqual(protocol['extra_pair_cap'],4383)
            self.assertEqual(protocol['embedding_text_limit'],2110)
            self.assertEqual(protocol['AI_max_physical_HTTP_per_pair'],1)
            self.assertGreater(protocol['budget_proposed']['conservative_model_and_embedding_tokens'],0)


class ScopeTests(unittest.TestCase):
    def test_installed_task_graph_keeps_learning_and_FS_commands(self):
        from configs.cle_weekly_reduced_20261028.install import update_plan
        saved=scope.CONTROL/'original_full/autonomy_plan.json'
        original=scope.read(saved if saved.exists() else scope.ROOT/'tools/cle_live_workbench/autonomy_plan.json')
        updated=update_plan(original)
        old={t['id']:t for t in original['tasks']};new={t['id']:t for t in updated['tasks']}
        self.assertEqual(old['Q.run'],new['Q.run']);self.assertEqual(old['FS.run'],new['FS.run'])
        self.assertEqual(new['Q.retest']['expected'],1416)
        self.assertEqual(new['GR.labels']['expected'],820)
        self.assertEqual(new['FR.run']['expected'],57)
        with tempfile.TemporaryDirectory() as temp:
            AutonomousPlan(Path(temp),updated)
        self.assertEqual(new['GR.extra']['depends'],['GR.decide82'])
        self.assertEqual(new['GR.train']['depends'],['GR.decide164'])

    def test_frozen_schedules_and_disjoint_enlargement(self):
        selection=scope.frozen_selection()
        self.assertEqual(len(selection['Q_intermediate_54']),54)
        self.assertEqual(len(selection['GR_first_82']),82)
        self.assertFalse(set(selection['GR_first_82']) & set(selection['GR_extra_82']))
        first=set(selection['FR_first_grow_27']+selection['FR_first_gate_30'])
        extra=set(selection['FR_extra_grow_27']+selection['FR_extra_gate_30'])
        self.assertEqual((len(first),len(extra)),(57,57)); self.assertFalse(first&extra)
        self.assertTrue(set(selection['FR_first_grow_27']+selection['FR_extra_grow_27'])<=set(selection['GR_first_82']))
        schedule=scope.read(scope.RUN/'FQ_RETEST/inputs/schedule.json')
        self.assertEqual(len(schedule),1416)
        counts={a:sum(c['condition']==a for c in schedule) for a in retest.CONDITIONS}
        self.assertEqual(counts,{'Q1':546,'Q2_K0':108,'Q2_K1':108,'Q2_K2':108,'Q2_K3':546})
        self.assertEqual(len({c['cell_id'] for c in schedule}),1416)

    def test_family_split_and_pool_counts(self):
        for package in ('FG_LABELS','FG_LABELS_EXTRA'):
            tasks=scope.read(scope.RUN/package/'inputs/tasks.json')
            split=scope.read(scope.RUN/package/'inputs/family_split.json')
            self.assertEqual(len(tasks),82)
            self.assertEqual(set(split['train_task_ids'])|set(split['development_task_ids']),set(tasks))
            self.assertFalse(set(split['train_families'])&set(split['development_families']))
        self.assertFalse(set(scope.read(scope.RUN/'FG_LABELS/inputs/family_split.json')['train_families'])&set(scope.read(scope.RUN/'FG_LABELS_EXTRA/inputs/family_split.json')['development_families']))

    def test_old_inputs_are_preserved_and_running_scopes_not_changed(self):
        old=scope.CONTROL/'original_full'
        self.assertEqual(scope.read(old/'FQ_RETEST/inputs/protocol.json')['planned_P7'],2730)
        self.assertEqual(scope.read(old/'FG_LABELS/inputs/protocol.json')['planned_P7'],2730)
        self.assertEqual(scope.read(old/'FR/inputs/protocol.json')['task_count'],571)
        self.assertEqual(scope.read(scope.RUN/'FFS/inputs/protocol.json')['planned_P7'],2980)
        self.assertEqual(scope.read(scope.RUN/'protocol.json')['parameters']['max_cards'] if 'parameters' in scope.read(scope.RUN/'protocol.json') else 3,3)

    def test_unstarted_guard_rejects_paid_prefix(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(scope,'RUN',Path(temp)):
            write_json(Path(temp)/'FG_LABELS/execution_index.json',{'segments':['old']})
            with self.assertRaisesRegex(ValueError,'cannot_reduce_started'):
                scope.ensure_unstarted('FG_LABELS')

    def test_pairing_does_not_include_unsampled_controls(self):
        rows=[]
        for tid,arm in [('1','Q1'),('1','Q2_K0'),('2','Q1')]:
            rows.append({'task_id':tid,'repeat':1,'condition':arm,'family_id':tid,'final':{'joint':True,'measured':True}})
        with patch.object(retest_analysis,'native_paired',return_value={'measured_pairs':1}) as calculate:
            result=retest_analysis.compare(rows,'Q2_K0','Q1',273)
            self.assertEqual({r['task_id'] for r in calculate.call_args.args[0]},{'1_r1'})
            self.assertEqual(result['planned_pairs'],108)

    def test_readiness_does_not_use_joint_point_estimate(self):
        labels=[{'task_id':str(i),'family_id':str(i),'preferred_level':'L1' if i<15 else 'L2'} for i in range(30)]
        model={'fit_task_ids':[str(i) for i in range(30)],'type':'multinomial_logistic'}
        dev={'classifier':[{'selected_level':'L1'},{'selected_level':'L2'}]}
        self.assertTrue(adaptive.readiness(labels,model,dev)['ready'])
        model['type']='constant'
        self.assertFalse(adaptive.readiness(labels,model,dev)['ready'])

    def test_omission_preserves_unexecuted_status_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            omit={'path':'decision.json','field':'action','values':['close_classifier_exploration']}
            task={'id':'optional','title':'optional','kind':'run','package':'FG_GATE','depends':[],
                  'expected':1788,'omit_when':omit}
            manager=AutonomousPlan(root,{'plan_id':'test','tasks':[task]})
            snap={'packages':[],'processes':[],'workers':0,'allowed':True}
            self.assertFalse(manager.native_done(task,snap))
            app.write_json(root/'decision.json',{'status':'decided','action':'close_classifier_exploration'})
            self.assertEqual(manager.reconcile(snap),[])
            self.assertEqual(manager.view['tasks'][0]['execution'],'not_required_by_protocol')
            self.assertFalse((root/'FG_GATE/summary.json').exists())

    def test_no_false_precision_for_insufficient_labels(self):
        records=[{'pair_ids':['p'],'card_to_pair':{'c':'p'},'traces':{'original':{'candidate_ids':['c']}}}]
        values,pending=adaptive.retrieval_statistics(records,{'p':'insufficient'})
        self.assertEqual(values,{}); self.assertEqual(pending,1)

    def test_process_recognition_and_worker_limit(self):
        processes=[{'ProcessId':1,'ParentProcessId':0,'CommandLine':'python -m configs.cle_weekly_reduced_20261028.granularity_extra run --workers 3'}]
        self.assertEqual(app.worker_processes(processes)[0]['package'],'FG_LABELS_EXTRA')
        self.assertEqual(app.worker_processes(processes)[0]['workers'],3)

    def test_enlargement_decision_has_bounded_negative_branch(self):
        tasks={}; rows=[]; labels=[{'preferred_level':'L1','any_memory_intervention':True},{'preferred_level':'L2','any_memory_intervention':True}]
        with patch.object(adaptive,'label_data',return_value=(tasks,rows,labels,{})), \
             patch.object(adaptive.ga,'fit_model',return_value={}), \
             patch.object(adaptive.ga,'development_results',return_value={}), \
             patch.object(adaptive,'readiness',return_value={'ready':False}), \
             patch.object(adaptive,'write'):
            self.assertEqual(adaptive.decide_gr(False)['action'],'expand')
            self.assertEqual(adaptive.decide_gr(True)['action'],'close_classifier_exploration')
            with patch.object(adaptive,'readiness',return_value={'ready':True}):
                self.assertEqual(adaptive.decide_gr(False)['action'],'freeze_and_gate')

    def test_no_diversity_closes_without_extra_API(self):
        labels=[{'preferred_level':'L1','any_memory_intervention':True}]
        with patch.object(adaptive,'label_data',return_value=({},[],labels,{})), \
             patch.object(adaptive.ga,'fit_model',return_value={}), \
             patch.object(adaptive.ga,'development_results',return_value={}), \
             patch.object(adaptive,'readiness',return_value={'ready':False}), \
             patch.object(adaptive,'write'):
            self.assertEqual(adaptive.decide_gr(False)['action'],'close_classifier_exploration')


if __name__=='__main__':
    unittest.main()
