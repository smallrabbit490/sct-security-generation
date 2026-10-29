"""代码变化足迹与已有外部依赖重定义的离线测量，不作Q路由或自动交付。

输入为两份已保存代码及公开题面；不用答案、隐藏测试或模型调用。语句变化代理
与Notion未取得的AST实现不同，只说明结构变化；既有分数仅用于事后关联。
"""
from __future__ import annotations

import argparse
import ast
import builtins
import csv
from difflib import SequenceMatcher
import json
from pathlib import Path
import symtable

from methods.sct_trajectory.public_contract_checks import compile_public_contract, check_public_contract


def _module_bindings(tree, *, include_imports=True):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            # 实际案例1364的仅类型声明、488的X=X不创建替代对象；150还通过globals读取。
            if isinstance(node, ast.AnnAssign) and node.value is None:
                continue
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Name)
                    and node.targets[0].id == node.value.id):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name))
        elif include_imports and isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or (alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name)
                         for alias in node.names)
    return names


def _external_reads(code, tree):
    symbols = symtable.symtable(code, '<saved-code>', 'exec')
    reads = set()
    def visit(table):
        reads.update(s.get_name() for s in table.get_symbols() if s.is_referenced() and s.is_global())
        for child in table.get_children():
            visit(child)
    visit(symbols)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'get' and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == 'globals'
                and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            reads.add(node.args[0].value)
    return reads - _module_bindings(tree) - set(dir(builtins))


def compare_code(old, new, public_task):
    """按前后代码计算可复算特征；编译失败记未测量，不当作零改动或风险通过。"""
    try:
        old_tree, new_tree = ast.parse(old), ast.parse(new)
    except SyntaxError as exc:
        return {'measured': False, 'error': 'syntax_error', 'error_line': exc.lineno,
                'statement_change_ratio': None, 'new_external_rebindings': None}
    statements = lambda tree: [ast.dump(n, include_attributes=False) for n in ast.walk(tree) if isinstance(n, ast.stmt)]
    before, after = statements(old_tree), statements(new_tree)
    changed = sum((j-i)+(l-k) for tag,i,j,k,l in SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
                  if tag != 'equal')
    denominator = len(before) + len(after)
    external = _external_reads(old, old_tree)
    new_definitions = _module_bindings(new_tree, include_imports=False)
    new_bindings = new_definitions - _module_bindings(old_tree)
    # 这是配对代码的候选影响边界，合法新定义仍可能出现，不能直接当作缺陷真值。
    rebound = sorted(external & new_bindings)
    contract = compile_public_contract(public_task)
    flags = lambda code: [v['rule_id'] for v in check_public_contract(code, contract)['violations']]
    return {'measured': True, 'error': None, 'old_empty': not old.strip(), 'new_empty': not new.strip(),
        'old_statement_count': len(before), 'new_statement_count': len(after),
        'changed_statement_events': changed, 'statement_denominator': denominator,
        'statement_change_ratio': changed / denominator if denominator else None,
        'zero_denominator_reason': None if denominator else 'both_codes_have_no_statements',
        'old_external_reads': sorted(external), 'new_external_rebindings': rebound,
        'new_imports_for_external_reads': sorted(external & (_module_bindings(new_tree) - new_definitions)),
        'old_public_contract_flags': flags(old), 'new_public_contract_flags': flags(new)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root
    out = root / 'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'
    target = out / 'footprint_replay'
    target.mkdir(exist_ok=False)
    with (out / 'historical_all_303_cases.csv').open(encoding='utf-8-sig', newline='') as handle:
        pairs = list(csv.DictReader(handle))
    online = root / 'translation_work/diagnostics/20261020/cle_q_online_v1'
    tasks = json.loads((online / 'tasks_D_init.json').read_text(encoding='utf-8'))
    new = {}
    for line in (online / 'D_init/rows.jsonl').open(encoding='utf-8'):
        row = json.loads(line)
        new[str(row['task_id'])] = row['final']
    results = []
    for pair in pairs:
        tid = pair['task_id']
        old = json.loads((root / pair['old_code_evidence']).read_text(encoding='utf-8'))['final']
        measured = compare_code(old['code'], new[tid]['code'], tasks[tid]['task_description'])
        results.append({'task_id': tid, 'family_id': pair['family_id'], 'transition': pair['transition'],
            'historical_verified_binding_defect': pair['historical_verified_binding_defect'] == 'True',
            'old_joint': old['joint'], 'new_joint': new[tid]['joint'],
            'both_formally_measured': old['measured'] and new[tid]['measured'], **measured})
    with (target / 'per_task.jsonl').open('w', encoding='utf-8') as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    groups = {}
    for transition in ['loss', 'rescue', 'both_pass', 'both_fail']:
        group = [r for r in results if r['transition'] == transition]
        analyzed = [r for r in group if r['measured'] and not r['old_empty'] and not r['new_empty']]
        ratios = [r['statement_change_ratio'] for r in analyzed if r['statement_change_ratio'] is not None]
        groups[transition] = {'tasks': len(group), 'nonempty_parsed_pairs': len(analyzed),
            'external_rebinding_flags': sum(bool(r['new_external_rebindings']) for r in analyzed),
            'historically_verified_binding_defects': sum(r['historical_verified_binding_defect'] for r in group),
            'mean_statement_change_ratio': sum(ratios)/len(ratios) if ratios else None}
    flagged = [r for r in results if r['measured'] and r['new_external_rebindings']]
    summary = {'protocol': 'cle-paired-code-footprint-v3-external-reference-forms',
        'scope': 'historical L1 vs Q2, both use memory; not no-memory counterfactual',
        'tasks': len(results), 'by_transition': groups,
        'external_rebinding_flag_ids': [r['task_id'] for r in flagged],
        'feature_not_a_defect_ground_truth': True,
        'formula': 'unmatched old plus unmatched new AST statement dumps / total statements; nested parent dumps included',
        'notion_AST_method_reproduced': False, 'threshold_calibration_done': False,
        'B04_promotion_gate_evaluated': False, 'Q_route_enabled': False,
        'API_calls': 0, 'new_generation_scores': 0,
        'limitations': ['Old/new histories and timing differ.', 'Paired code feature needs two available candidates.',
                        'Static binding flags can reflect legitimate edits.', 'Missing/invalid code is separate from zero change.']}
    (target / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
