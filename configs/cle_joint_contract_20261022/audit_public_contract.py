"""复查原 D_init 源码的公开契约静态缺陷；零 API、零执行、零正式重评分。

公开规则仅由 task_description 编译。参考 concat 只作为第二组被检查源码，
不参与规则提取；原 Joint/F/S/measured 只用于关联分层，不回流生成或 Q 授信。
保留原任务/结果的路径和 SHA256，逐尝试明细单独写入忽略的运行区。
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import warnings


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from methods.sct_trajectory.public_contract_checks import check_public_contract, compile_public_contract


INPUT_ROOT = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1'
RAW_DEFAULT = ROOT / 'translation_work/diagnostics/20261022/cle_joint_contract/public_contract_audit_v2'
SUMMARY_DEFAULT = ROOT / 'results/curated/cle_joint_contract_20261022/public_contract_audit.json'


def digest(value) -> str:
    """记录原始字节或确定性 JSON 身份；不把哈希当作语义正确证据。"""
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def relative(path: Path) -> str:
    """仓库内保存相对路径，外部输入保留其明确绝对路径。"""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """仅创建新明细文件；拒绝覆盖已有诊断。"""
    with path.open('x', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def result_counts(rows: list[dict]) -> dict:
    """按原记录标签分层计数；静态发现不改变任何原 Joint 标签。"""
    flagged = [row for row in rows if row['checks']['violations']]
    return {
        'records': len(rows),
        'with_static_violations': len(flagged),
        'by_rule': dict(sorted(Counter(v['rule_id'] for row in flagged for v in row['checks']['violations']).items())),
        'original_joint_true': sum(row.get('original_joint') is True for row in rows),
        'original_joint_false': sum(row.get('original_joint') is False for row in rows),
        'original_joint_unknown': sum(row.get('original_joint') not in (True, False) for row in rows),
        'flagged_original_joint_true': sum(row.get('original_joint') is True for row in flagged),
        'flagged_original_joint_false': sum(row.get('original_joint') is False for row in flagged),
        'flagged_original_measured_false': sum(row.get('original_measured') is False for row in flagged),
        'flagged_empty_code': sum(row['code_chars'] == 0 for row in flagged),
        'records_with_unmeasured_planned_rules': sum(bool(row['checks']['unmeasured_check_ids']) for row in rows),
    }


def main() -> None:
    """固定输入全量扫描后写新摘要；缺任务、重复、final/attempt 不一致则停止。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', type=Path, default=INPUT_ROOT / 'tasks_D_init.json')
    parser.add_argument('--rows', type=Path, default=INPUT_ROOT / 'D_init/rows.jsonl')
    parser.add_argument('--raw-dir', type=Path, default=RAW_DEFAULT)
    parser.add_argument('--output', type=Path, default=SUMMARY_DEFAULT)
    args = parser.parse_args()
    if args.raw_dir.exists() or args.output.exists():
        raise FileExistsError('audit_outputs_already_exist_choose_new_paths_no_overwrite')
    task_bytes = args.tasks.read_bytes()
    row_bytes = args.rows.read_bytes()
    tasks = json.loads(task_bytes)
    rows = [json.loads(line) for line in row_bytes.splitlines() if line.strip()]
    if not isinstance(tasks, dict) or len(tasks) != 303 or len(rows) != 303:
        raise ValueError('expected_current_303_task_303_final_snapshot')
    row_ids = [str(row['task_id']) for row in rows]
    if len(set(row_ids)) != len(row_ids) or set(row_ids) != set(tasks):
        raise ValueError('task_result_assignment_contract_failed')

    attempts = []
    finals = []
    references = []
    contracts = []
    warnings.filterwarnings('ignore', category=SyntaxWarning)
    for row in rows:
        task_id = str(row['task_id'])
        task = tasks[task_id]
        # 此调用先于读取 ground_truth；唯一规则来源是公开字段。
        public = task['task_description']
        requirements = compile_public_contract(public)
        contracts.append({'task_id': task_id, 'public_contract_sha256': digest(public), 'requirements': requirements})
        per_task_attempts = []
        for index, attempt in enumerate(row['attempts']):
            if not isinstance(attempt.get('code'), str):
                raise ValueError(f'attempt_code_not_string:{task_id}:{index}')
            if not all(isinstance(attempt.get(key), bool) for key in ('functional', 'security', 'joint', 'measured')):
                raise ValueError(f'original_result_boolean_contract_failed:{task_id}:{index}')
            if attempt['joint'] != (attempt['functional'] and attempt['security']):
                raise ValueError(f'original_joint_identity_failed:{task_id}:{index}')
            item = {
                'task_id': task_id, 'attempt': attempt.get('attempt'), 'source_attempt_index': index,
                'code_sha256': digest(attempt['code']), 'code_chars': len(attempt['code']),
                'original_joint': attempt['joint'], 'original_functional': attempt['functional'],
                'original_security': attempt['security'], 'original_measured': attempt['measured'],
                'checks': check_public_contract(attempt['code'], requirements),
            }
            per_task_attempts.append(item)
            attempts.append(item)
        final = row['final']
        matches = [(source, record) for source, record in zip(row['attempts'], per_task_attempts)
                   if source.get('attempt') == final.get('attempt') and source['code'] == final.get('code')]
        if len(matches) != 1:
            raise ValueError(f'final_code_does_not_match_one_original_attempt:{task_id}')
        source, record = matches[0]
        if any(source[key] != final.get(key) for key in ('functional', 'security', 'joint', 'measured')):
            raise ValueError(f'final_evidence_disagrees_with_original_attempt:{task_id}')
        finals.append({**record, 'original_row_error_type': row.get('error_type')})

        # 参考只被静态审计，不执行，也不用于修改上面的 requirements。
        ground = task['ground_truth']
        reference = ground['code_before'] + ground['patched_code'] + ground['code_after']
        references.append({'task_id': task_id, 'code_sha256': digest(reference), 'code_chars': len(reference),
                           'checks': check_public_contract(reference, requirements)})

    checker_path = ROOT / 'methods/sct_trajectory/public_contract_checks.py'
    metadata = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'git_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python_version': platform.python_version(),
        'inputs': {
            'tasks': {'path': relative(args.tasks), 'sha256': digest(task_bytes)},
            'rows': {'path': relative(args.rows), 'sha256': digest(row_bytes)},
        },
        'sources': {
            relative(Path(__file__)): digest(Path(__file__).read_bytes()),
            relative(checker_path): digest(checker_path.read_bytes()),
        },
        'public_rule_source': 'task_description only; no setup/test/reference used to derive rules',
        'reference_composition': 'code_before + patched_code + code_after; static inspection only',
        'API_calls': 0, 'candidate_executions': 0, 'new_model_generations': 0,
        'original_records_modified': False, 'formal_scores_recomputed_or_changed': False,
        'data_contract_checks': {'task_row_bijection': True, 'original_joint_equals_F_and_S': True,
                                 'final_code_and_labels_match_exactly_one_attempt': True},
    }
    coverage = {
        'public_contracts': len(contracts),
        'entry_point_known': sum(bool(row['requirements']['entry_point']) for row in contracts),
        'signature_known': sum(bool(row['requirements']['signature']) for row in contracts),
        'tasks_with_explicit_protected_bindings': sum(bool(row['requirements']['protected_bindings']) for row in contracts),
        'explicit_protected_bindings': sum(len(row['requirements']['protected_bindings']) for row in contracts),
    }
    flagged_finals = [{key: row[key] for key in ('task_id', 'attempt', 'code_sha256', 'code_chars',
                                               'original_joint', 'original_measured', 'original_row_error_type')}
                      | {'violation_ids': [item['id'] for item in row['checks']['violations']]}
                      for row in finals if row['checks']['violations']]
    summary = {
        'protocol': 'public_contract_static_audit_v2',
        'scope': 'historical_static_diagnostic_not_new_policy_or_Joint_results',
        'measurement_schema': 'explicit_measured_and_unmeasured_rule_partition',
        'metadata': metadata,
        'contract_coverage': coverage,
        'original_attempts': result_counts(attempts),
        'original_finals': result_counts(finals),
        'reference_static_checks': {
            'records': len(references),
            'with_static_violations': sum(bool(row['checks']['violations']) for row in references),
            'flagged_task_ids': [row['task_id'] for row in references if row['checks']['violations']],
            'dynamic_correctness': 'unmeasured',
        },
        'flagged_finals': flagged_finals,
        'interpretation_limits': [
            'No new CLE generation or model-policy Joint score is established by these checks.',
            'Historical association does not show that repair will recover all or any flagged failures.',
            'Empty code flags identify original generation failures, not additional semantic-repair opportunities.',
            'No findings in these references or historical Joint passes does not establish universal zero false positives.',
            'The checker covers only explicit bindings and recognizable interfaces; semantic behavior, dynamic binding and card implementation remain partly or wholly unmeasured.',
        ],
        'raw_artifacts': {name: relative(args.raw_dir / filename) for name, filename in (
            ('contracts', 'contracts.jsonl'), ('attempts', 'attempts.jsonl'),
            ('finals', 'finals.jsonl'), ('references', 'references.jsonl'), ('manifest', 'manifest.json'))},
    }
    args.raw_dir.mkdir(parents=True, exist_ok=False)
    for filename, content in [('contracts.jsonl', contracts), ('attempts.jsonl', attempts),
                              ('finals.jsonl', finals), ('references.jsonl', references)]:
        write_jsonl(args.raw_dir / filename, content)
    with (args.raw_dir / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    summary['raw_artifact_sha256'] = {name: digest((args.raw_dir / Path(path).name).read_bytes())
                                      for name, path in summary['raw_artifacts'].items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'summary': relative(args.output), 'attempts': len(attempts),
                      'finals_flagged': len(flagged_finals),
                      'references_flagged': summary['reference_static_checks']['with_static_violations'],
                      'API_calls': 0, 'candidate_executions': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
