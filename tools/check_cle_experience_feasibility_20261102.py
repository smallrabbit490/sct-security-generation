"""零 API：复用三题族的已保存交付代码，比较简单契约检查和卡片行为检查。"""
import ast
import builtins
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = Path(__file__).resolve().parents[1] / 'results/curated/cle_experience_feasibility_20261102'
Q = ROOT / 'probe_relay_20261028/Q.retest'
GR = ROOT / 'FG_LABELS'
CARD_IDS = {
    '1152': ['hint-94-7278376456866242101', 'hint-95-44902294748858938'],
    '497': ['pitfall-352-694839719183572027'],
    '1023': ['pitfall-862-5818189147437479149'],
}

def evaluate(payload):
    """仅执行已保存代码及公开契约诊断，不调用项目模型或原隐藏测试。"""
    code, task = payload['code'], payload['task']
    allowed = {'ast', 'operator', 'math', 're', 'json', 'collections', 'typing', 'unicodedata', 'decimal', 'codecs', 'inspect'}
    original_import = builtins.__import__
    def limited_import(name, *args, **kwargs):
        if name.split('.')[0] not in allowed:
            raise RuntimeError('local diagnostic import blocked: ' + name)
        return original_import(name, *args, **kwargs)
    def no_open(*args, **kwargs):
        raise RuntimeError('file access disabled in saved code')
    env = {'__builtins__': dict(vars(builtins), __import__=limited_import, open=no_open), '__name__': 'saved_candidate'}
    checks = []
    def check(group, name, action):
        try:
            passed = bool(action())
            error = None
        except Exception as exc:
            passed, error = False, type(exc).__name__ + ': ' + str(exc)[:160]
        checks.append(dict(group=group, name=name, passed=passed, error=error))
    def rejects(fn, arg):
        try:
            fn(arg)
        except ValueError:
            return True
        return False
    exec(compile(code, '<saved-code>', 'exec'), env)
    function_name = {'1152': 'evaluate_expression', '497': 'validate_json_request', '1023': 'update_privileges'}[task]
    if function_name not in env:
        return [dict(group='simple', name='required function exists', passed=False, error='missing public entry point')]
    if task == '1152':
        fn = env['evaluate_expression']
        check('simple', 'ordinary arithmetic 7+3*2', lambda: fn('7+3*2') == 13)
        check('simple', 'reject function call', lambda: rejects(fn, 'abs(1)'))
        check('experience', 'signed decimal -.5+2', lambda: fn('-.5+2') == 1.5)
        check('experience', 'negative nested operand 7-(-2)', lambda: fn('7-(-2)') == 9)
        # Broad source-card operators conflict with target + - * /; retain as rejected-rule controls.
        check('inapplicable_raw_rule', 'source card accepts exponent 2**3', lambda: fn('2**3') == 8)
        check('inapplicable_raw_rule', 'source card accepts scientific notation 1e2', lambda: fn('1e2') == 100)
    elif task == '497':
        fn = env['validate_json_request']
        def req(body='{"a":7}', kind=dict):
            return kind(headers=kind({'Content-Type': 'application/json'}), body=body)
        check('simple', 'ordinary valid JSON object', lambda: fn(req()) == {'a': 7})
        check('simple', 'reject malformed JSON', lambda: rejects(fn, req('{')))
        class DictChild(dict):
            pass
        check('experience', 'dict subtype with same valid content', lambda: fn(req(kind=DictChild)) == {'a': 7})
        # Target declares dict; widening to arbitrary Mapping has no target-contract guarantee.
        from collections import UserDict
        check('inapplicable_raw_rule', 'source card accepts arbitrary Mapping', lambda: fn(req(kind=UserDict)) == {'a': 7})
    else:
        fn = env['update_privileges']
        tree = ast.parse(code)
        rebound = any(isinstance(n, (ast.Assign, ast.AnnAssign)) and any(isinstance(x, ast.Name) and x.id == 'USERS' for x in ast.walk(n)) for n in tree.body)
        check('simple', 'do not replace host USERS', lambda: not rebound)
        def call(actor, target, role, expected, old_role='normal'):
            env['USERS'] = {7: {'role': 'admin'}, 8: {'role': old_role}, 9: {'role': 'normal'}}
            result = fn(actor, target, role)
            return result is expected and (not expected or env['USERS'][target]['role'] == role)
        check('simple', 'admin changes another user', lambda: call(7, 8, 'moderator', True))
        check('simple', 'ordinary user cannot grant admin', lambda: call(9, 8, 'admin', False) and env['USERS'][8]['role'] == 'normal')
        check('experience', 'normal role remains a valid destination', lambda: call(7, 8, 'normal', True, 'moderator'))
        check('experience', 'idempotent role update succeeds', lambda: call(7, 8, 'normal', True))
        # Source card forbids sole-admin demotion; target does not specify this policy.
        check('inapplicable_raw_rule', 'source card forbids sole-admin demotion', lambda: call(7, 7, 'normal', False))
    return checks

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for task, root in [('1152', Q), ('497', Q), ('1023', GR)]:
        rows = {}
        for segment in json.loads((root / 'execution_index.json').read_text(encoding='utf-8'))['segments']:
            for path in sorted((Path(segment) / 'task_rows').glob(task + '_r*.json')):
                row = json.loads(path.read_text(encoding='utf-8'))
                rows[row['cell_id']] = (path, row)
        for cell, (path, row) in sorted(rows.items()):
            final = row['final']
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', __file__, '--child'], input=json.dumps({'task': task, 'code': final['code']}), text=True, capture_output=True, timeout=12)
            if result.returncode:
                raise RuntimeError(cell + ': ' + result.stderr)
            checks = json.loads(result.stdout)
            simple_ok = all(x['passed'] for x in checks if x['group'] == 'simple')
            exp_fail = any(not x['passed'] for x in checks if x['group'] == 'experience')
            records.append(dict(task_id=task, family_id=row['family_id'], cell_id=cell, source=str(path), model_cohort=row.get('model_cohort'), native_joint=final['joint'], native_measured=final['measured'], simple_pass=simple_ok, experience_flags=exp_fail, incremental_flag=simple_ok and exp_fail, checks=checks))
    summary = dict(model_API_calls=0, embedding_API_calls=0, scope='retrospective feasibility on 3 selected families; not held-out performance', cells=len(records), families=len({r['family_id'] for r in records}), incremental_flag_cells=[r['cell_id'] for r in records if r['incremental_flag']], incremental_flag_families=len({r['family_id'] for r in records if r['incremental_flag']}), correct_native_cells=sum(r['native_joint'] and r['native_measured'] for r in records), experience_flags_on_native_correct=[r['cell_id'] for r in records if r['native_joint'] and r['native_measured'] and r['experience_flags']], raw_inapplicable_flags_on_native_correct=[{'cell_id': r['cell_id'], 'checks': [x['name'] for x in r['checks'] if x['group'] == 'inapplicable_raw_rule' and not x['passed']]} for r in records if r['native_joint'] and r['native_measured'] and any(x['group'] == 'inapplicable_raw_rule' and not x['passed'] for x in r['checks'])])
    cards = {c['invariant_id']: c for c in map(json.loads, (ROOT / 'shared_inputs/memory1939_q0.jsonl').read_text(encoding='utf-8').splitlines())}
    excerpts = {task: [{'id': cid, 'applicability': cards[cid]['applicability'], 'negative_guardrail': cards[cid]['negative_guardrail'], 'fix_directive': cards[cid]['source']['fix_directive']} for cid in ids] for task, ids in CARD_IDS.items()}
    (OUT / 'checks.json').write_text(json.dumps({'summary': summary, 'card_sources': excerpts, 'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    if '--child' in sys.argv:
        print(json.dumps(evaluate(json.loads(sys.stdin.read())), ensure_ascii=False))
    else:
        main()
