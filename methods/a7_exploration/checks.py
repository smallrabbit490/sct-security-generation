"""公开任务自生成检查与本地执行；不接触官方 setup、答案或测试，不写经验库。"""
from __future__ import annotations
import ast
import json
import os
import re
from pathlib import Path
import sys
import tempfile
from methods.direction_screening.run import ROOT
from methods.a7_exploration.protocol import classify_exception,public_task

FORBIDDEN={'socket','http','requests','httpx','ftplib','smtplib','subprocess','ctypes','multiprocessing'}


def snippet_error(code,case=False):
    """公开测试结构门控；网络、进程、动态执行禁止，断言必须确实运行。"""
    try:
        tree=ast.parse(code)
    except (SyntaxError,TypeError):
        return 'check_syntax_error'
    if case and not any(isinstance(n,ast.Assert) for n in tree.body):
        return 'missing_top_level_assertion'
    if case:
        for statement in tree.body:
            if not isinstance(statement,ast.Assert) and any(isinstance(n,ast.Assert) for n in ast.walk(statement)):
                return 'conditionally_executed_or_swallowed_assertion'
    if case and any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree)):
        return 'uncalled_test_definition'
    for node in ast.walk(tree):
        modules=[]
        if isinstance(node,ast.Import):
            modules=[a.name.split('.')[0] for a in node.names]
        elif isinstance(node,ast.ImportFrom):
            modules=[(node.module or '').split('.')[0]]
        if isinstance(node,ast.ImportFrom) and (node.module or '').startswith('urllib') and node.module!='urllib.parse':
            return 'unsupported_dependency'
        if isinstance(node,ast.Import) and any(a.name.startswith('urllib') and a.name!='urllib.parse' for a in node.names):
            return 'unsupported_dependency'
        if any(m in FORBIDDEN or m not in sys.stdlib_module_names for m in modules):
            return 'unsupported_dependency'
        if case and isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='candidate':
            return 'candidate_must_be_callable_alias'
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('exec','eval','__import__'):
            return 'dynamic_check_code'
    return ''


def derivation_matches(code,decision):
    """审核的独立预期值与直接常量断言需一致；避免 supported=true 与推导矛盾。"""
    expected=decision.get('expected_result')
    text=str(decision.get('derivation','')).lower()
    if re.search(r'(?:should|must|expected (?:result|output)(?: should)?)(?:\s+be|\s+return|\s+is)?\s+false',text) and expected is True:
        return False
    if re.search(r'(?:should|must|expected (?:result|output)(?: should)?)(?:\s+be|\s+return|\s+is)?\s+true',text) and expected is False:
        return False
    for node in ast.walk(ast.parse(code)):
        if isinstance(node,ast.Assert) and isinstance(node.test,ast.Compare):
            comparison=node.test
            if isinstance(comparison.left,ast.Call) and isinstance(comparison.left.func,ast.Name) and comparison.left.func.id=='candidate':
                if len(comparison.ops)==1 and isinstance(comparison.ops[0],(ast.Eq,ast.Is)) and isinstance(comparison.comparators[0],ast.Constant):
                    if expected!=comparison.comparators[0].value: return False
    return True


def propose(task,session,previous_errors=None):
    """公开契约→公开夹具及用例→语义复核；没有来源补丁/目标答案，复核仍可能错误。"""
    context=json.dumps(public_task(task),ensure_ascii=False)
    result={'setup':'','cases':[],'errors':[],'origin':'public_contract_only',
            'semantic_review':'same_model_not_independent_proof'}
    try:
        value=session.json('Create runnable Python checks ONLY from the public contract below. '
            'Return JSON {"setup":"imports and runtime fixtures", "cases":[{"id":"f1",'
            '"kind":"functional or security","purpose":"exact public-contract justification",'
            '"code":"top-level snippet with assert"}]}. Generate as many useful distinct checks as '
            'supported; prefer distinct representative cases, remove redundant variants. Every case gets a fresh setup and candidate module. '
            'setup runs in the target function globals BEFORE candidate loading; it may define caller-provided '
            'classes/globals only when explicitly named in the contract. Fixtures are synthetic examples, '
            'not new requirements. Do not supply unspecified global data. Standard library only, no network '
            'or child processes. Cases run with candidate alias and the same module globals. Call candidate, '
            'not the original function name. candidate IS THE FUNCTION: use candidate(args), NEVER candidate.function_name(args). '
            'Use empty setup when no runtime fixture is needed; add only useful imports. '
            'Every case MUST finish with a top-level assert. Do not place assertions inside try, if or '
            'loops; exceptions could swallow them and conditional branches could skip them. '
            'Test expected exceptions with try/except and a FINAL top-level assertion '
            'that the required exception was raised. Do not assert invented values or unspecified edge cases. '
            'Omit cases with ambiguous expected behavior. Do not define uncalled test functions. '
            'Use tempfile for files; avoid long/resource-intensive attacks. Do not invent timing thresholds. '
            'Previous rejected-check feedback: '+json.dumps(previous_errors or [])+' Task: '+context,'checks_propose')
        setup=value.get('setup','')
        if not isinstance(setup,str) or snippet_error(setup):
            raise ValueError('invalid_public_setup')
        cases=[]
        seen=set()
        for c in value.get('cases',[]):
            if not isinstance(c,dict) or not all(isinstance(c.get(k),str) for k in ('id','kind','purpose','code')):
                result['errors'].append('invalid_case_schema'); continue
            err=snippet_error(c['code'],True)
            if err or c['id'] in seen or c['kind'] not in ('functional','security'):
                result['errors'].append(err or 'invalid_case'); continue
            seen.add(c['id']); cases.append(c)
        reviewed=session.json('Review public setup and checks solely against this public task. '
            'Reject unsupported fixtures/globals, invented requirements, wrong expected values/exceptions, '
            'checks that fail because imports/globals are missing, and overly strict security boundaries. '
            'Ordinary standard-library imports are permitted; unnecessary harmless imports alone are not '
            'grounds to reject the entire setup. Reject individual invalid cases independently. '
            'Return JSON {"setup_approved":true,"approved_ids":["case IDs"],"reason":"rationale"}. '
            'If setup is unsupported reject all cases depending on it. No candidate or reference answer is available. '
            'Task: '+context+'\nProposed: '+json.dumps({'setup':setup,'cases':cases}), 'checks_review')
        approved=reviewed.get('approved_ids',[])
        if reviewed.get('setup_approved') is not True:
            result['errors'].append('setup_semantic_rejection:'+str(reviewed.get('reason',''))); return result
        result.update(setup=setup,cases=[c for c in cases if c['id'] in approved],
                      proposed_count=len(cases),review_reason=reviewed.get('reason',''))
        # 同模型第一次审核会漏掉编码后字符变化与臆造边界；第二次独立上下文逐例推导。
        derived=session.json('Audit each assertion by DERIVING its expected result from explicit public '
            'requirements step by step. You have no candidate code or reference answer. First apply '
            'normalization/URL decoding specified by task; then validation rules. Example: percent-encoded '
            'space becomes a space; a list allowing letters/digits and punctuation does not automatically '
            'allow spaces. Do not confuse encoded input with decoded allowed characters. Empty inputs, '
            'non-string inputs, URL schemes, email syntax edge cases, whitespace normalization and exact '
            'exception choices are unsupported unless the task determines them. Reject assertions swallowing '
            'AssertionError, invented time thresholds, or ambiguous expected outputs. Ordinary canonical '
            'valid examples and explicit invalid characters may be tested. Return JSON '
            '{"cases":[{"id":"case ID","supported":true,"assertion_matches_derivation":true,'
            '"expected_result":null,"derivation":"exact requirement to expected output"}]}. '
            'expected_result must be the independently derived JSON value for direct literal assertions. '
            'If assertion demands True but your reasoning derives False, set assertion_matches_derivation=false '
            'and supported=false. Ambiguous behavior is unsupported; do not choose an interpretation. '
            'Task: '+context+'\nSetup: '+setup+'\nCases: '+json.dumps(result['cases']), 'checks_expected_derivation')
        decisions={c['id']:c for c in derived.get('cases',[]) if isinstance(c,dict) and 'id' in c}
        result['expected_derivations']=decisions
        result['cases']=[c for c in result['cases'] if decisions.get(c['id'],{}).get('supported') is True
                         and decisions.get(c['id'],{}).get('assertion_matches_derivation') is True
                         and derivation_matches(c['code'],decisions[c['id']])]
    except Exception as exc:
        result['cases']=[]
        result['errors'].append(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
    return result


WORKER=r'''
import json,sys,traceback
from pathlib import Path
p=json.loads(Path('input.json').read_text(encoding='utf-8'))
def audit(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn','os.fork'):
        raise PermissionError('network_and_child_process_forbidden')
sys.addaudithook(audit)
phase='setup'
try:
    ns={'__name__':'candidate_module'}
    exec(compile(p['setup'],'<public_setup>','exec'),ns)
    phase='candidate_compile'
    obj=compile(p['code'],'<candidate>','exec')
    phase='candidate_load'
    exec(obj,ns)
    ns['candidate']=ns[p['entry']]
    phase='check'
    exec(compile(p['check'],'<public_check>','exec'),ns)
    result={'status':'pass','measured':True,'phase':phase}
except BaseException as exc:
    result={'exception_type':type(exc).__name__,'phase':phase,
            'error':''.join(traceback.format_exception(type(exc),exc,exc.__traceback__))[-1600:]}
Path('result.json').write_text(json.dumps(result),encoding='utf-8')
'''


def execute(code,entry,suite,timeout=10):
    """候选与公开检查→逐例独立 python -I；超时/依赖事故缺测，不读取官方测试。"""
    from translation_pipeline.persistent_container import run_limited_command
    result={'cases':[],'measured':False,'static_security':'unmeasured','type_check':'unmeasured'}
    root=ROOT/'translation_work/temp/a7_checks'
    root.mkdir(parents=True,exist_ok=True)
    for c in suite.get('cases',[]):
        row={k:c[k] for k in ('id','kind','purpose')}
        err=snippet_error(c['code'],True) or snippet_error(suite.get('setup',''))
        if err:
            row.update(status='invalid_check',measured=False,error=err)
            result['cases'].append(row); continue
        with tempfile.TemporaryDirectory(dir=root,prefix='case_') as folder:
            d=Path(folder)
            (d/'worker.py').write_text(WORKER,encoding='utf-8')
            (d/'input.json').write_text(json.dumps({'setup':suite.get('setup',''),'code':code,
                'entry':entry,'check':c['code']}),encoding='utf-8')
            env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ}
            env.update(TEMP=folder,TMP=folder)
            try:
                rc,stdout,stderr,timed=run_limited_command([sys.executable,'-I','worker.py'],d,
                    timeout=timeout,env=env,output_limit=2000)
                if timed or not (d/'result.json').exists():
                    row.update(status='timeout' if timed else 'worker_error',measured=False)
                else:
                    row.update(json.loads((d/'result.json').read_text(encoding='utf-8')))
                    if 'exception_type' in row:
                        status,measured=classify_exception(row['exception_type'],row['phase'])
                        if row['phase']=='setup': status,measured='invalid_setup',False
                        row.update(status=status,measured=measured)
            except Exception as exc:
                row.update(status='environment_error',measured=False,error_type=type(exc).__name__)
        result['cases'].append(row)
    result['measured']=any(c.get('measured') for c in result['cases'])
    return result
