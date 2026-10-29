"""修复锁定名单已观察的数据/环境缺陷，另存v2；不换题、不调用模型。

只恢复固定上游的URL夹具、补名称/类型级公开依赖，以及修订两份有明确错误的
离线参考代码。所有变化分别记账；不把测试值或修订后的目标参考送给生成器。
"""
from __future__ import annotations

import ast
import copy
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from .prepare import CONFIG, OUT, read, write
from configs.cle_dgrow_url_repair_20261019.repair_and_retest import SOURCE, REVISION


def missing_declarations(task):
    """在审查端定位外部依赖，只导出名称/类型/形参，不导出配置值或函数体。"""
    gt = task['ground_truth']
    ref = ast.parse(gt['code_before'] + gt['patched_code'] + gt['code_after'])
    used = {n.id for n in ast.walk(ref) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    public = json.dumps(task['task_description'], ensure_ascii=False)
    declarations = []
    for node in ast.parse(task['unittest']['setup']).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in used and not re.search(r'\b'+re.escape(target.id)+r'\b', public):
                    types = {ast.Dict: 'dict', ast.List: 'list', ast.Set: 'set', ast.Tuple: 'tuple', ast.Constant: 'constant'}
                    kind = types.get(type(node.value), 'provided configuration object')
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'compile':
                        kind = 'compiled regular-expression object'
                    declarations.append(f'{target.id}: {kind}, supplied by the host; use the supplied object without replacing it.')
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in used and not re.search(r'\b'+re.escape(node.name)+r'\b', public):
            if isinstance(node, ast.FunctionDef):
                args = ', '.join(a.arg for a in node.args.args)
                declarations.append(f'{node.name}({args}): host-provided helper for the operation described in the task; do not redefine it.')
            else:
                declarations.append(f'{node.name}: host-provided class; preserve the supplied type.')
    return declarations


def main():
    destination = OUT / 'v2'
    destination.mkdir(exist_ok=False)
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        upstream = {str(t['index']): t for t in json.load(response)}
    manifest = read(CONFIG / 'manifest.json')
    changes, all_tasks = [], []
    for group in manifest['groups']:
        original = read(OUT / f'tasks_{group}.json')
        tasks = copy.deepcopy(original)
        for task in tasks:
            tid = str(task['index'])
            modifications = []
            if tid in {'1301', '1092', '645', '1094', '657', '660'}:
                source = upstream[tid]
                assert task['CWE_ID'] == source['CWE_ID'] and task['ground_truth'] == source['ground_truth']
                assert '<LOCAL_PATH>' in task['unittest']['testcases']
                assert '<LOCAL_PATH>' not in source['unittest']['testcases']
                # 1301连setup的字典键都被脱敏合并，必须同时恢复，不能只修testcases。
                for field in ['setup', 'testcases']:
                    if task['unittest'][field] != source['unittest'][field]:
                        assert '<LOCAL_PATH>' in task['unittest'][field]
                        task['unittest'][field] = source['unittest'][field]
                        modifications.append('unittest.' + field)
            if tid == '108':
                old_code = task['ground_truth']['patched_code']
                assert "if '..' in local_part" in old_code
                task['ground_truth']['patched_code'] = old_code + "\n    if local_part.startswith('.'):\n        return False"
                modifications.append('reference_only: reject leading-dot local part required by existing safety test')
            if tid == '87':
                task['ground_truth']['patched_code'] = (
                    "\n    log_pattern = re.compile(r'([^\\[\\]\\r\\n]+)\\[([^\\[\\]\\r\\n]+)\\]\\s*:\\s*(.*)')")
                modifications.append('reference_only: match the public LOG_LEVEL[TIMESTAMP] : MESSAGE format')
            context = task['task_description'].get('context', '')
            if tid == '468':
                context = re.sub(r'\bdatabase\b', 'user_database', context)
                context = context.replace('EXPECTED_CSRF_TOKEN', 'VALID_CSRF_TOKEN')
                modifications.append('public.context: correct database and CSRF binding names; no values')
            if tid == '1016':
                context = re.sub(r'\bUSERS\b', 'SYSTEM_USERS', context)
                modifications.append('public.context: correct SYSTEM_USERS binding name; no values')
            task['task_description']['context'] = context
            declarations = missing_declarations(task)
            if declarations:
                task['task_description']['context'] += '\nHost-provided dependencies (names and types only):\n- ' + '\n- '.join(declarations)
                modifications.append('public.context: declare supplied dependencies without configuration values')
            if modifications:
                changes.append({'task_id': tid, 'group': group, 'changes': modifications,
                    'declarations': declarations, 'original_preserved': True,
                    'test_values_added_to_public_context': False})
            task['_study_group'] = group
            all_tasks.append(task)
        write(destination / f'tasks_{group}.json', tasks)
    receipt = {'protocol': 'cle-memory-mechanisms-data-contract-v2', 'selection_unchanged': True,
        'upstream_revision': REVISION, 'source_url': SOURCE, 'changes': changes,
        'reference_only_patch_ids': ['108', '87'], 'fixture_restoration_ids': ['1301', '1092', '645', '1094', '657', '660'],
        'prior_scores_rewritten': False, 'model_generations': 0, 'API_calls': 0}
    write(destination / 'repair_receipt.json', receipt)

    # 仅在这个新预检进程补齐已安装的命令工具，不安装、不改变系统PATH，不改变验证器。
    git_bin = r'C:\Program Files\Git\usr\bin'
    for executable in ('echo.exe', 'cat.exe'):
        assert os.path.isfile(os.path.join(git_bin, executable))
    os.environ['PATH'] = git_bin + os.pathsep + os.environ['PATH']
    from methods.cle_ablation.retrieval_q_study import reference_check
    from methods.cle_ablation.joint_contract import official_evaluate
    from configs.cle_dgrow_url_repair_20261019.repair_and_retest import reference
    raw = destination / 'reference_preflight'
    raw.mkdir()

    def check(task):
        result = reference_check(task)
        result.update(group=task['_study_group'], family_id=task['family_id'],
                      remaining_helper_declarations=missing_declarations(task))
        # 首次失败的题保留完整原验证证据，既不降低安全规则，也不使用新验证器。
        if str(task['index']) in {'108', '1301', '1092', '645', '1094', '657', '660', '87', '1346'}:
            result['full_validation'] = official_evaluate('PLT', task, reference(task))
        write(raw / f"{task['index']}.json", result)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = [future.result() for future in as_completed([pool.submit(check, t) for t in all_tasks])]
    records.sort(key=lambda r: (r['group'], r['task_id']))
    summary = {'protocol': receipt['protocol'], 'planned': 96, 'completed': len(records),
        'reference_joint_pass': sum(r['state'] == 'A' for r in records),
        'reference_and_dependency_checks_pass': sum(r['passed'] and not r['remaining_helper_declarations'] for r in records),
        'failed_ids': [r['task_id'] for r in records if not r['passed'] or r['remaining_helper_declarations']],
        'selection_unchanged': True, 'runtime_executable_path_prepend': git_bin,
        'runtime_profile_required_for_all_future_arms': True, 'original_validator_unchanged': True,
        'public_contract_review': 'Agent dependency-and-name review; not a human relevance-label signoff',
        'reference_pass_does_not_prove_public_contract_completeness': True,
        'API_calls': 0, 'new_model_generations': 0, 'Q_updates': 0, 'records': records}
    write(destination / 'reference_preflight.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
