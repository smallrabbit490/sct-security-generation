"""已完成共享初析实验的零API代码/契约诊断；保留原8题主结果，辅助子集另列。"""
import ast
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation.audit_memory_q import read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write

RUN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/shared_initial8'
CURATED = ROOT/'results/curated/cle_memory_q_shared_initial8_20261016'
PROVIDED = {'1341': ['xml_template'], '1000': ['BLOG_FORMAT'], '1013': ['USERS', 'USER_PROFILES'],
            '1055': ['PERMITTED_FIELDS'], '340': [], '777': ['ALLOWED_COMMANDS'], '1001': [],
            '1015': ['USERS', 'USER_PROFILES']}


def main():
    analysis = json.loads((RUN/'analysis.json').read_text(encoding='utf-8'))
    rows = read_rows(RUN/'compare/rows.jsonl')
    mechanism = json.loads((RUN/'attempt_analysis.json').read_text(encoding='utf-8'))
    dataset = {str(t['index']): t for t in json.loads((ROOT/'data/external/secodeplt/secodeplt/data.json').read_text(encoding='utf-8'))}
    defects, bindings, code_records = [], [], []
    for tid, names in PROVIDED.items():
        setup = ast.parse(dataset[tid]['unittest']['setup'])
        assigned = {n.id for n in ast.walk(setup) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        missing = sorted(set(names)-assigned)
        bindings.append({'task_id': tid, 'public_provided_names': names,
                         'setup_assigned_names': sorted(assigned), 'missing_public_names': missing})
        if missing:
            defects.append(tid)
    for row in rows:
        tid = str(row['task_id'])
        for attempt in row['attempts']:
            tree = ast.parse(attempt['code'])
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == dataset[tid]['task_description']['function_name'])
            assignments = {n.id for statement in tree.body if isinstance(statement, (ast.Assign, ast.AnnAssign))
                           for n in ast.walk(statement) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            code_records.append({'task_id': tid, 'arm': row['arm'], 'attempt': attempt['attempt'],
                'signature_args': [a.arg for a in function.args.args],
                'overridden_provided_globals': sorted(assignments & set(PROVIDED[tid])),
                'syntax_valid': True, 'workflow_completed': attempt['generation']['workflow_completed']})
    prepared = read_rows(RUN/'compare/shared_initial.jsonl')
    initial_failures = [str(r['task_id']) for r in prepared if r['error_type']]
    sensitivity = []
    for label, excluded in [('exclude_observed_contract_defect', set(defects)),
                            ('exclude_contract_defect_and_common_initial_failure', set(defects+initial_failures))]:
        counts = {}
        for arm in ('Q1','Q2','Q3'):
            subset = [r for r in rows if r['arm'] == arm and str(r['task_id']) not in excluded]
            counts[arm] = {'n':len(subset), **{k:sum(r['final'][k] for r in subset) for k in ('functional','security','joint')}}
        sensitivity.append({'label':label,'excluded_task_ids':sorted(excluded),'arms':counts,'post_hoc_descriptive_only':True})
    rescues = []
    for task in analysis['tasks']:
        if task['Q2_vs_Q1'] != 'rescue':
            continue
        items = [a for a in mechanism if a['task_id'] == task['task_id']]
        rescues.append({'task_id':task['task_id'], 'Q2_rank_changed': task['Q2_order_changed'],
                        'all_arms_all_attempts_selected_cards':sum(len(a['actual_ranked_ids']) for a in items),
                        'all_arms_all_attempts_adopted_cards':sum(len(a['adopted_ids']) for a in items)})
    bank = {n['invariant_id']:n for n in read_rows(RUN/'compare/input_memory.jsonl')}
    promoted = [{'task_id':a['task_id'],'attempt':a['attempt'],'card_id':i,
                 'q_value':bank[i]['q_value'],'q_visits':bank[i]['q_visits']}
                for a in mechanism if a['arm']=='Q2' for i in a['new_cards_adopted']]
    result = {'model_calls':0,'embedding_calls':0,'primary_denominator_unchanged':8,
        'public_context_bindings':bindings, 'post_run_contract_defect_tasks':defects,
        'preflight_limitation':'Public review and passing reference missed a runtime global-name mismatch; original rows/scores preserved, no replacement or paid rerun.',
        'shared_initial_failed_tasks':initial_failures, 'post_hoc_sensitivity':sensitivity,
        'Q2_vs_Q1_rescues':rescues, 'q_promoted_adopted_cards':promoted,
        'all_attempts_syntax_valid':len(code_records), 'code_diagnostics':code_records,
        'workflow_incomplete_attempts':sum(not c['workflow_completed'] for c in code_records),
        'Q2_c0_set_changed_tasks':len({a['task_id'] for a in mechanism if a['arm']=='Q2' and a['attempt']==0 and a['set_changed_vs_sim']}),
        'Q2_c0_order_changed_tasks':len({a['task_id'] for a in mechanism if a['arm']=='Q2' and a['attempt']==0 and a['order_changed_vs_sim']}),
        'conclusion':'No demonstrated Q-attributable Joint gain; observed sole rescue has no selected/adopted cards. No escalation.'}
    write(RUN/'diagnosis.json',result)
    write(CURATED/'diagnosis.json',result)
    shutil.copy2(RUN/'replay/replay_summary.json',CURATED/'replay_summary.json')
    readme = (CURATED/'README.md').read_text(encoding='utf-8').replace('# 最新Q库8题三臂机制探针','# 共享首次初析8题三臂机制实验',1)
    readme = readme.replace('原生P7、同CWE打乱Q；仅D_gate开发诊断。','原P7的共享c0初析控制变体，c1独立；同CWE打乱Q，仅D_gate开发诊断。',1)
    readme += ('\n## 归因与成本补充\n\n'
        'Q2多通过的1013题所有臂均无选入/采用卡，不能归功于Q。1015公开USERS与夹具USER_DETAILS不一致，预检漏项保留；主表不删题。'
        '诊断性去掉1015和共享初析失败1013后，三臂Joint均2/6；这是事后辅助分析。\n\n'
        '共享初析8次/11956 Token只记一次；加三臂共148次LLM调用、456630 Token。Embedding另25次/30157 Token。'
        '零API回放见replay_summary.json，契约/代码诊断见diagnosis.json。\n\n'
        '[完整结论](../../../docs/CLE_Q回放与共享初析8题实验_20261016.md)。\n')
    (CURATED/'README.md').write_text(readme,encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('post_run_contract_defect_tasks','shared_initial_failed_tasks',
        'post_hoc_sensitivity','Q2_vs_Q1_rescues','q_promoted_adopted_cards','all_attempts_syntax_valid')},ensure_ascii=False))


if __name__ == '__main__':
    main()
