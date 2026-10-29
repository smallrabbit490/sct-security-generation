"""验证迁移的实际P7控制、技术门与模型接线；全部为离线测试。"""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from configs.cle_v41_migration_20261025 import run
from methods.cle_ablation import runner


class MigrationTest(unittest.TestCase):
    def test_schedule_probe_is_included_not_extra(self):
        p=run.read(run.ROOT/'configs/cle_v41_migration_20261025/protocol.json')
        cells=run.schedule(p)
        self.assertEqual(len(cells),24)
        self.assertEqual(sum(len(c['arms']) for c in cells),48)
        self.assertEqual([c['group'] for c in cells[:4]],['technical']*4)
        self.assertEqual(len({c['pair_id'] for c in cells}),24)
        self.assertEqual({c['task_id'] for c in cells[:4]},{'1256','100'})

    def test_empty_arm_keeps_native_P7_reanalysis_and_repair(self):
        calls=[];queries=[]
        initial={'vulnerability_hypothesis':['risk'], 'functional_invariants':['preserve behavior']}
        def request(prompt):
            calls.append(str(prompt))
            if str(prompt).startswith('Generate complete'):
                value='def add(a,b):\n    return a+b'
            elif str(prompt).startswith('Plan the implementation'):
                value=json.dumps({'Preserved_Func':'add','Patch_Scope':'body'})
            else:
                value=json.dumps(initial)
            return {'choices':[{'message':{'content':value},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
        def provider(query):
            queries.append(copy.deepcopy(query));return run.empty_provider(query)
        task={'index':1}
        evidence={'functional':{'status':'fail'},'security':{'status':'pass'}}
        with patch.object(runner,'plt_contract',return_value={'task_id':'1','description':'add a and b'}), \
             patch('methods.sct_trajectory.closed_loop.validate_and_state',return_value=(evidence,{})):
            row=runner.run_one('PLT',task,'P7',request,{'full':[]},initial_analysis=initial,
                               retrieval_provider=provider)
        self.assertEqual(len(row['attempts']),2)
        self.assertEqual(len(queries),2)
        self.assertEqual(queries[0]['current_code'],'')
        self.assertIn('return a+b',queries[1]['current_code'])
        for a in row['attempts']:
            self.assertEqual(a['generation']['cards'],[])
            self.assertIn('experience_analysis',[s['stage'] for s in a['generation']['stages']])
        row['migration_arm']='E0'
        self.assertEqual(run.technical_errors(row),[])

    def test_technical_gate_rejects_degraded_even_when_code_passes(self):
        row={'migration_arm':'E1','attempts':[{'measured':True,'joint':True,
             'generation':{'workflow_completed':True,'stages':[{'stage':'planning','status':'degraded'}]},
             'retrieval_trace':{'status':'completed'}}]}
        self.assertEqual(run.technical_errors(row),['planning:degraded'])

    def test_contract_model_parameter_reaches_request_and_metadata(self):
        source=(run.ROOT/'methods/cle_ablation/run_joint_contract.py').read_text(encoding='utf-8')
        self.assertIn("parser.add_argument('--model', default='deepseek-v3.2'",source)
        self.assertIn('_requester(args.model, 60',source)
        self.assertIn("'model': args.model",source)
        self.assertNotIn("_requester('deepseek-v3.2'",source)


if __name__=='__main__':unittest.main()
