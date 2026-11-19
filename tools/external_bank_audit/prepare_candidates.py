"""冻结五库审计输入；按生成/补全原模式分离题面、断言和静态oracle。"""
import collections
import hashlib
import json
from pathlib import Path

from prepare import ROOT, BASE, item, read, source

OUT = ROOT / 'translation_work/diagnostics/20261118/candidate_six_rule_audit'
BANKS = ['AutoSUIT', 'PythonSecurityEval', 'LSCBench-Function', 'CodeLMSec', 'SafeCoder']


def autosuit_sources(path, row):
    """仅Task1给定题述和保存文件约定；不把参考实现/patching输入当成公开信息。"""
    public = 'Task 1: Secure Code Generation\n' + row['code_description']
    public += '\nSave generated code as: ' + row['code_file_name']
    result = [source(path, 'public', public)]
    for kind in ('functional', 'security'):
        if row.get(kind + '_test'):
            s = source(path, 'test', row[kind + '_test'])
            s['suite'] = kind
            s['upstream_filename'] = row[kind + '_test_file']
            # 同行功能/安全文本不能用同一个(path,role)覆盖。
            s['path'] += '#' + row[kind + '_test_file']
            result.append(s)
    return result


def prepare():
    rows = []
    p = BASE / 'autosuit/upstream_20261118'
    for lang in ('python', 'java', 'c', 'cpp'):
        f = p / lang / 'test.jsonl'
        for row in map(json.loads, read(f).splitlines()):
            oracle = 'dynamic_function_security' if row.get('security_test') else 'dynamic_function_only'
            r = item('AutoSUIT', row['id'], lang, autosuit_sources(f, row), oracle)
            r['input_mode'] = 'Task1_secure_code_generation'
            rows.append(r)
    p = BASE / 'pythonsecurityeval/upstream_20261118/data/PythonSecurityEval'
    for f in sorted(p.rglob('text.txt')):
        ss = [source(f, 'public')]
        for test in f.parent.iterdir():
            if test.name.lower() == 'unit_test.py':
                ss.append(source(test, 'test'))
        rows.append(item('PythonSecurityEval', f.parent.name, 'python', ss, 'dynamic_function_static_security'))
    p = BASE / 'lscbench_function/upstream_20261118/tasks'
    for task in sorted(p.glob('*_function')):
        import tomllib
        meta = tomllib.loads(read(task / 'task.toml'))
        ss = [source(task / 'instruction.md', 'public')]
        # test.sh/split_axes只负责调度与解析，不是题目具体断言。
        for f in sorted((task / 'tests').rglob('*')):
            if f.is_file() and f.suffix in ('.py', '.sh', '.json', '.yaml', '.yml'):
                ss.append(source(f, 'test' if f.name in ('test_func.py', 'test_vuln.py') else 'test_driver'))
        r = item('LSCBench-Function', task.name, meta['metadata']['language'], ss, 'dynamic_function_security')
        r['evidence_boundary'] = 'Only downloaded instruction and verifier files. Project substrate/call sites and most concrete assertions live in task images and are NOT supplied here. Do not infer absence from unavailable image contents; verdict cannot certify whole-task adequacy.'
        r['full_context_available'] = False
        rows.append(r)
    p = BASE / 'codelmsec/upstream_20261118/benchmark/benchmark_data'
    for f in sorted(p.rglob('*')):
        if f.suffix in ('.py', '.c'):
            rows.append(item('CodeLMSec', f.relative_to(p).as_posix(), f.suffix[1:], [source(f, 'public')], 'static_only'))
    p = BASE / 'safecoder/upstream_20261118/data_eval/sec_eval'
    query_root = ROOT / 'translation_work/downloads/codeql/query-source/github-codeql-e637eb7'
    for f in sorted(p.rglob('info.json')):
        info = json.loads(read(f))
        ss = [source(x, 'public') for x in sorted(f.parent.glob('*context.*'))]
        ss.append(source(f, 'static_rule'))
        query = info.get('check_ql', '').split('codeql-repo/')[-1]
        q = query_root / query
        if q.is_file():
            ss.append(source(q, 'static_rule'))
        r = item('SafeCoder', f.parent.relative_to(p).as_posix(), info['language'], ss, 'static_only')
        r['input_mode'] = 'original_code_completion_file_context_plus_func_context'
        r['source_group'] = f.relative_to(p).parts[0]
        rows.append(r)
    counts = collections.Counter(r['bank'] for r in rows)
    assert dict(counts) == dict(zip(BANKS, (951, 470, 150, 280, 81))), counts
    assert len({r['key'] for r in rows}) == 1932
    OUT.mkdir(parents=True, exist_ok=True)
    raw = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    target = OUT / 'payloads.jsonl'
    if target.exists() and target.read_text(encoding='utf-8') != raw:
        raise RuntimeError('Frozen payload differs; use a new run directory')
    target.write_text(raw, encoding='utf-8')
    inventory = {'tasks': len(rows), 'planned_judgments': 2 * len(rows), 'payload_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'by_bank': {b: {'tasks': n, 'with_assertion_sources': sum(any(s['role'] == 'test' for s in r['sources']) for r in rows if r['bank'] == b), 'max_chars': max(sum(len(s['text']) for s in r['sources']) for r in rows if r['bank'] == b)} for b, n in counts.items()}}
    (OUT / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(inventory, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    prepare()
