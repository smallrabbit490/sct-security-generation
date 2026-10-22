"""独立恢复32道D_grow网址题，复用原验证器补测；不调用模型或更新Q。"""
from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.sct_trajectory.closed_loop import validate_and_state

CONFIG = Path(__file__).resolve().parent
OUT = ROOT / 'translation_work/diagnostics/20261019/cle_dgrow_url_repair_v2'
CURATED = ROOT / 'results/curated/cle_dgrow_url_repair_20261019'
DATA = ROOT / 'data/external/secodeplt/secodeplt/data.json'
QUAL = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v2/qualification.after_dependencies.json'
HISTORY = ROOT / 'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
PROTOCOL = 'cle-dgrow-url-source-restoration-public-contract-v2'
REVISION = '1f3da9ee48e0046359903cba0cc48d03665f96d5'
SOURCE = f'https://raw.githubusercontent.com/ucsb-mlsec/SeCodePLT/{REVISION}/virtue_code_eval/data/safety/secodeplt/data.json'
DESCRIPTIONS = {
    'ALLOWED_DOMAINS': 'allowed URL hostnames',
    'SAFE_REDIRECT_DOMAINS': 'allowed redirect hostnames',
    'ALLOWED_REDIRECT_DOMAINS': 'allowed redirect hostnames',
    'TRUSTED_DOMAIN_LIST': 'allowed redirect hostnames',
    'VALID_REDIRECT_DOMAINS': 'allowed redirect hostnames',
    'TRUSTED_IMAGE_HOSTS': 'allowed image hostnames',
    'ALLOWED_SCHEMES': 'allowed URL schemes',
    'APPROVED_API_DOMAINS': 'allowed API hostnames',
    'INTERNAL_IP_RANGES': 'blocked hostname or IP address prefixes',
    'ALLOWED_API_DOMAINS': 'allowed API hostnames',
    'INTERNAL_IP_PATTERNS': 'blocked hostname or IP address prefixes',
    'TRUSTED_RSS_PROVIDERS': 'allowed RSS feed hostnames',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(task, secure=True):
    gt = task['ground_truth']
    return gt['code_before'] + gt['patched_code' if secure else 'vulnerable_code'] + gt['code_after']


def declarations(task):
    """仅导出依赖名称和类型，禁止把夹具配置值放进公开题面。"""
    used = {n.id for n in ast.walk(ast.parse(reference(task)))
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    public = json.dumps(task['task_description'], ensure_ascii=False)
    missing = {}
    for node in ast.parse(task['unittest']['setup']).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in used:
                    if not re.search(r'\b' + re.escape(target.id) + r'\b', public):
                        value = ast.literal_eval(node.value)
                        assert isinstance(value, list) and all(isinstance(v, str) for v in value)
                        missing[target.id] = 'list[str]: ' + DESCRIPTIONS[target.id]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name in used and not re.search(r'\b' + re.escape(name) + r'\b', public):
                    missing[name] = f'imported from {node.module}.{alias.name}'
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                if name in used and not re.search(r'\b' + re.escape(name) + r'\b', public):
                    missing[name] = f'module {alias.name}'
    return missing


def prepare():
    if shutil.disk_usage(ROOT.anchor).free < 1024 ** 3:
        raise RuntimeError('insufficient_disk_space')
    OUT.mkdir(parents=True, exist_ok=False)
    local = read(DATA)
    old_qualification = read(QUAL)
    selected = sorted([r for r in old_qualification['tasks'] if str(r['cwe']) in {'601', '918'}],
                      key=lambda r: int(r['task_id']))
    assert len(selected) == 32 and all(not r['reward_eligible'] for r in selected)
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        upstream = json.load(response)
    restored, changes, originals, public_overrides = [], [], [], {}
    for row in selected:
        task_id = int(row['task_id'])
        original, source = local[task_id], upstream[task_id]
        assert original['index'] == source['index'] == task_id
        assert original['CWE_ID'] == source['CWE_ID'] == row['cwe']
        assert original['ground_truth'] == source['ground_truth']
        assert original['unittest']['setup'] == source['unittest']['setup']
        assert original['install_requires'] == source['install_requires']
        assert '<LOCAL_PATH>' not in json.dumps(source)
        fields = ['unittest.testcases']
        for key in original['task_description']:
            if original['task_description'][key] != source['task_description'][key]:
                assert key == 'security_policy' and task_id == 1399
                fields.append('task_description.' + key)
        task = copy.deepcopy(source)
        missing = declarations(task)
        if missing:
            addition = '\n\nExternal runtime bindings supplied before this code executes:\n'
            addition += '\n'.join(f'- `{name}`: {kind}.' for name, kind in sorted(missing.items()))
            addition += '\nUse the existing configuration bindings; do not redefine their values.'
            task['task_description']['context'] += addition
            fields.append('task_description.context')
        assert not declarations(task)
        task['family_id'] = row['family_id']
        restored.append(task)
        originals.append(source)
        public_overrides[str(task_id)] = task['task_description']
        changes.append({'task_id': str(task_id), 'cwe': row['cwe'], 'family_id': row['family_id'],
                        'restored_fields': fields, 'declared_bindings': missing,
                        'old_exclusion_reasons': row['exclusion_reasons'],
                        'source_reference_unchanged': True, 'test_setup_unchanged': True})
    metadata = {'protocol': PROTOCOL, 'task_ids': [r['task_id'] for r in selected],
                'source_url': SOURCE, 'upstream_revision': REVISION,
                'source_blob': '70bb25ff204e61f36d447d5787cc2869d9be0649',
                'original_dataset_sha256': digest(DATA),
                'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'runner': 'configs/cle_dgrow_url_repair_20261019/repair_and_retest.py',
                'python_executable': sys.executable,
                'backend': 'original validate_and_state / local python -I',
                'retest': ['upstream_secure_reference', 'upstream_vulnerable_control',
                           'historical_observe_final_code', 'historical_retest_final_code'],
                'new_generation': False, 'API_calls': 0, 'Q_updates': 0,
                'old_results_modified': False, 'status': 'prepared'}
    write(OUT / 'upstream_selected_tasks.json', originals)
    write(CONFIG / 'repaired_tasks.json', restored)
    write(CONFIG / 'public_task_descriptions.json', public_overrides)
    write(CONFIG / 'repair_manifest.json', {**metadata, 'changes': changes})
    write(OUT / 'run_metadata.json', metadata)
    shutil.copy2(Path(__file__), OUT / 'runner_snapshot.py')
    print(json.dumps({'prepared_tasks': len(restored), 'context_repaired': sum(bool(c['declared_bindings']) for c in changes)}, ensure_ascii=False))


def measured(evidence):
    """已观测setup缺依赖：必须确有两组测试执行，环境异常不计有效测量。"""
    metadata = evidence.get('metadata', {})
    groups = metadata.get('test_groups', {})
    return (not metadata.get('worker_error')
            and all(groups.get(k, {}).get('total', 0) > 0 for k in ('capability', 'safety'))
            and all(evidence[k]['status'] in {'pass', 'fail'} for k in ('functional', 'security')))


def retest(workers):
    metadata = read(OUT / 'run_metadata.json')
    assert metadata['status'] == 'prepared'
    assert digest(DATA) == metadata['original_dataset_sha256']
    tasks = {str(t['index']): t for t in read(CONFIG / 'repaired_tasks.json')}
    old = {r['task_id']: r for r in read(QUAL)['tasks']}
    jobs = [(i, 'secure_reference', reference(t), None) for i, t in tasks.items()]
    jobs += [(i, 'vulnerable_control', reference(t, False), None) for i, t in tasks.items()]
    historical_missing = []
    for cohort in ('observe', 'retest'):
        source = HISTORY / cohort / 'rows.jsonl'
        seen = set()
        with source.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                i = str(row['task_id'])
                if i not in tasks:
                    continue
                assert i not in seen
                seen.add(i)
                final = row['final']
                provenance = {'rows_path': str(source.relative_to(ROOT)),
                              'old_functional': final['functional'], 'old_security': final['security'],
                              'old_joint': final['joint'], 'old_measured': final['measured'],
                              'original_attempt': final['attempt'],
                              'historical_generation_error': final['generation'].get('error_type'),
                              'historical_workflow_completed': final['generation'].get('workflow_completed')}
                if not final['code'].strip():
                    historical_missing.append({'task_id': i, 'cohort': cohort, 'reason': 'empty_historical_code'})
                    continue
                jobs.append((i, cohort, final['code'], provenance))
        historical_missing.extend({'task_id': i, 'cohort': cohort, 'reason': 'missing_historical_row'}
                                  for i in tasks.keys() - seen)

    def check(job):
        i, cohort, code, provenance = job
        evidence, state = validate_and_state(tasks[i], code, timeout=20)
        item = {'protocol': PROTOCOL, 'task_id': i, 'cwe': tasks[i]['CWE_ID'],
                'family_id': tasks[i]['family_id'], 'cohort': cohort,
                'validation': {'evidence': evidence, 'state': state},
                'functional': evidence['functional']['status'] == 'pass',
                'security': evidence['security']['status'] == 'pass',
                'joint': state == 'A', 'measured': measured(evidence), 'code': code,
                'historical_provenance': provenance, 'API_calls': 0, 'Q_updates': 0}
        write(OUT / 'validation' / cohort / (i + '.json'), item)
        return item

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item in pool.map(check, jobs):
            results.append(item)
            if len(results) % 32 == 0:
                print(json.dumps({'validated': len(results), 'planned': len(jobs)}), flush=True)
    with (OUT / 'rows.jsonl').open('x', encoding='utf-8') as stream:
        for item in results:
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    summary = {'protocol': PROTOCOL, 'planned_tasks': len(tasks), 'new_generation': False,
               'API_calls': 0, 'Q_updates': 0, 'historical_missing': historical_missing, 'cohorts': {}}
    for cohort in ('secure_reference', 'vulnerable_control', 'observe', 'retest'):
        rows = [r for r in results if r['cohort'] == cohort]
        summary['cohorts'][cohort] = {'planned': 32, 'executed': len(rows),
            'measured': sum(r['measured'] for r in rows),
            'unmeasured': sum(not r['measured'] for r in rows),
            'functional': sum(r['functional'] for r in rows),
            'security': sum(r['security'] for r in rows), 'joint': sum(r['joint'] for r in rows),
            'states': dict(Counter(r['validation']['state'] for r in rows))}
    refs = {r['task_id']: r for r in results if r['cohort'] == 'secure_reference'}
    negative = {r['task_id']: r for r in results if r['cohort'] == 'vulnerable_control'}
    qualification = []
    for i, task in tasks.items():
        row = refs[i]
        qualifies = row['joint'] and row['measured'] and not declarations(task)
        qualification.append({'task_id': i, 'cwe': task['CWE_ID'], 'family_id': task['family_id'],
            'previous_reward_eligible': old[i]['reward_eligible'], 'reward_eligible_new_protocol': qualifies,
            'reference_state': row['validation']['state'],
            'vulnerable_security_failed': negative[i]['measured'] and not negative[i]['security'],
            'original_qualification_modified': False})
    summary['reward_eligible_new_protocol'] = sum(q['reward_eligible_new_protocol'] for q in qualification)
    summary['negative_control_security_rejected'] = sum(q['vulnerable_security_failed'] for q in qualification)
    assert digest(DATA) == metadata['original_dataset_sha256']
    summary['original_dataset_unchanged'] = True
    write(OUT / 'qualification.repaired.json', qualification)
    write(OUT / 'summary.json', summary)
    CURATED.mkdir(parents=True, exist_ok=True)
    write(CURATED / 'summary.json', summary)
    with (CURATED / 'scores.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        fields = ['task_id', 'cwe', 'cohort', 'functional', 'security', 'joint', 'measured',
                  'old_joint', 'historical_workflow_completed']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in results:
            provenance = r['historical_provenance'] or {}
            writer.writerow({**{k: r[k] for k in fields[:7]},
                             'old_joint': provenance.get('old_joint', ''),
                             'historical_workflow_completed': provenance.get('historical_workflow_completed', '')})
    write(CURATED / 'qualification.json', qualification)
    metadata.update(status='completed', actual_validations=len(results))
    write(OUT / 'run_metadata.json', metadata)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'retest'])
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    prepare() if args.command == 'prepare' else retest(args.workers)
