"""把七个冻结快照适配为完整审计材料，严格分离公开输入、参考和测试。"""
import collections
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/external'
OUT = ROOT / 'translation_work/diagnostics/20261117/external_bank_audit'


def read(p):
    return p.read_text(encoding='utf-8-sig', errors='replace')


def source(p, role, text=None):
    return {'path': p.relative_to(ROOT).as_posix(), 'role': role, 'text': read(p) if text is None else text}


def bundle(folder, role):
    if not folder.exists():
        return []
    return [source(p, role) for p in sorted(folder.rglob('*')) if p.is_file() and p.suffix.lower() in
            ('.py', '.c', '.cpp', '.h', '.java', '.js', '.ts', '.go', '.json', '.xml', '.yaml', '.yml', '.txt', '.md', '.html', '.ql', '.en-us') and p.name not in ('package-lock.json',)]


def item(bank, task, lang, sources, oracle):
    return {'bank': bank, 'task_id': task, 'key': f'{bank}/{task}', 'language': lang,
            'oracle': oracle, 'sources': sources}


def prepare():
    rows = []
    p = BASE / 'cweval/upstream_20261117'
    for f in sorted((p/'benchmark').rglob('*_task.*')):
        full = read(f)
        # 与上游generate._get_cases一致：BEGIN SOLUTION前才是公开题面。
        public = full.split('BEGIN PROMPT')[-1]
        anchor = next(line for line in public.splitlines() if 'BEGIN SOLUTION' in line)
        public = public.split(anchor)[0].strip()
        tests = f.with_name(f.stem.replace('_task', '_test') + '.py')
        wrapper=read(p/'cweval/ppt/__init__.py').split("PPT = '''",1)[1].split("'''",1)[0]
        ss = [source(f, 'public', public), source(p/'cweval/ppt/__init__.py','public',wrapper), source(f, 'reference', full)]
        if tests.exists(): ss.append(source(tests, 'test'))
        rows.append(item('CWEval', f.relative_to(p/'benchmark').as_posix(), f.suffix[1:], ss, 'dynamic_function_security'))
    p = BASE / 'securityeval/upstream_20261117'; f=p/'dataset.jsonl'
    for r in [json.loads(l) for l in read(f).splitlines() if l.strip()]:
        rows.append(item('SecurityEval', r['ID'], 'py', [source(f,'public',r['Prompt']), source(f,'reference_insecure',r['Insecure_code'])], 'static_only'))
    p = BASE / 'llmseceval/upstream_20261117'; f=p/'Dataset/LLMSecEval-Prompts_dataset.json'
    for row_index,r in enumerate(json.loads(read(f))):
        task=r['Prompt ID']; pub=r.get('Manually-fixed NL Prompt')
        if not isinstance(pub,str) or not pub.strip(): pub=r['LLM-generated NL Prompt']
        ss=[source(f,'public',pub)]
        for candidate in (p/'Dataset/Secure Code Samples').rglob(task+'.*'):
            if candidate.is_file(): ss.append(source(candidate,'reference'))
        for candidate in (p/'Dataset/Security Unit Tests').rglob('*'):
            if candidate.is_file() and (candidate.stem==task or candidate.stem=='test_'+task):
                ss.append(source(candidate,'test' if candidate.stat().st_size else 'test_placeholder'))
        record=item('LLMSecEval',task,str(r.get('Language')),ss,'partial_dynamic_security')
        record['key']+=f'/row-{row_index}'
        record['upstream_row_index']=row_index
        rows.append(record)
    p=BASE/'sallm/upstream_20261117'; f=p/'Dataset/dataset.jsonl'
    for r in [json.loads(l) for l in read(f).splitlines() if l.strip()]:
        prefix=r['technique']+'_'+r['source']+'_'; filename=r['id'][len(prefix):]
        folder=p/'Dataset'/r['technique']/r['source']; ss=[source(f,'public',r['prompt']),source(f,'reference_insecure',r['insecure_code'])]
        for candidate in sorted(folder.iterdir()):
            if candidate.is_file() and (candidate.name=='test_'+filename or candidate.name.startswith(Path(filename).stem+'_')):
                ss.append(source(candidate,'test' if candidate.name=='test_'+filename else 'dependency'))
        rows.append(item('SALLM',r['id'],'py',ss,'mixed_dynamic_static'))
    p=BASE/'codeguard_plus/upstream_20261117'
    for f in sorted((p/'data/base').rglob('info.json')):
        r=json.loads(read(f)); relative=f.parent.relative_to(p/'data/base'); ss=[]
        for candidate in sorted(f.parent.iterdir()):
            if candidate.name!='info.json' and candidate.is_file(): ss.append(source(candidate,'public'))
        for s in bundle(p/'unit_test'/relative,'test'):
            if Path(s['path']).name=='test_case.py':s['role']='reference'
            ss.append(s)
        ss.append(source(f,'static_rule'))
        rows.append(item('CodeGuard+',relative.as_posix(),r['language'],ss,'dynamic_function_static_security'))
    p=BASE/'cyberseceval/upstream_20261117'; f=p/'CybersecurityBenchmarks/datasets/instruct/instruct-v2.json'
    for r in json.loads(read(f)):
        ss=[source(f,'public',r['test_case_prompt']),source(f,'reference_insecure',r.get('origin_code','')),
            source(f,'static_rule',json.dumps({k:r.get(k) for k in ('cwe_identifier','rule','analyzer','pattern_desc')},ensure_ascii=False))]
        rows.append(item('CyberSecEval',str(r['prompt_id']),r['language'],ss,'static_only'))
    p=BASE/'seccodebench_v2/upstream_20261117'
    for lang,file in [('python','python.json'),('cpp','c.json'),('go','go.json'),('java','java.json'),('nodejs','nodejs.json')]:
        tasks=json.loads(read(p/'datasets/benchmark'/lang/file))
        # 官方verify URL精确映射至验证项目，避免拿错同语言题的测试。
        for task,r in tasks.items():
            prompt=p/'datasets/benchmark'/lang/'prompts'/(r['prompt']+'.en-US')
            template=p/'datasets/templates'/lang/r['template']
            ss=[source(prompt,'public')]
            for s in bundle(template,'public'):
                # 固定native gen模式；不能把fix/security-aware指南混入公开题面。
                if '/test' not in s['path'].lower() and '/resources/' not in s['path'].lower(): ss.append(s)
            url=r['verify_urls']['gen']; route=url.split('/verify/',1)[-1]
            model=p/'docker/model'/lang
            if lang=='python': candidates=[model/'python_bench'/route]
            elif lang=='java':
                mapping=json.loads(read(model/'datasets/benchmark/java/java.json'))
                verifier_task=mapping.get(route,{})
                candidates=[model/'datasets/templates/java'/verifier_task['template']] if verifier_task else []
            else:
                candidates=[d for d in model.rglob('*') if d.is_dir() and d.name==route]
            # 不把验证服务和全库测试当作一道题的上下文。
            for folder in candidates:
                for s in bundle(folder,'reference'):
                    path=s['path']; name=Path(path).name.lower()
                    if name.endswith('.en-us'):
                        s['role']='judge_rubric'
                    elif '/test' in path.lower() or name.startswith('test') or name.endswith('test.java') or name.endswith('_test.go'):
                        s['role']='test'
                    elif name in ('requirements.txt','pom.xml','package.json','go.mod','signature.json'):
                        s['role']='dependency'
                    ss.append(s)
            rows.append(item('SecCodeBench-V2',lang+'/'+task,lang,ss,'dynamic_function_security_or_configured_judge'))
    counts=collections.Counter(r['bank'] for r in rows)
    assert dict(counts)=={'CWEval':119,'SecurityEval':121,'LLMSecEval':150,'SALLM':100,'CodeGuard+':103,'CyberSecEval':1681,'SecCodeBench-V2':98},counts
    assert len({r['key'] for r in rows})==2372
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'payloads.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    inventory={k:{'tasks':counts[k], 'with_dynamic_test':sum(any(s['role']=='test' for s in r['sources']) for r in rows if r['bank']==k),
                  'max_chars':max(sum(len(s['text']) for s in r['sources']) for r in rows if r['bank']==k)} for k in counts}
    (OUT/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(inventory,ensure_ascii=False,indent=2))


if __name__=='__main__': prepare()
