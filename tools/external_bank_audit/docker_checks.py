"""容器内执行真实参考/不安全对照测试与静态完整性检查，不调用模型。"""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK=Path('/work')
INPUT=Path('/inputs')
RESULT=[]


def command(label, argv, cwd, timeout=180, env=None):
    current=os.environ.copy()
    if env:current.update(env)
    try:
        r=subprocess.run(argv,cwd=cwd,env=current,capture_output=True,text=True,timeout=timeout)
        obj={'check':label,'command':argv,'returncode':r.returncode,'stdout':r.stdout[-18000:],'stderr':r.stderr[-6000:]}
    except subprocess.TimeoutExpired:
        obj={'check':label,'command':argv,'returncode':None,'error':'timeout'}
    RESULT.append(obj)
    (WORK/'checks.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2))
    print(label,obj['returncode'],flush=True)
    return obj


def main():
    live=WORK/'checks';live.mkdir(exist_ok=True)
    src=INPUT/'cweval'; dest=live/'cweval'
    if not dest.exists():shutil.copytree(src,dest)
    command('toolchain_versions',['sh','-c','python --version; gcc --version | head -1; javac -version; mvn --version | head -2; node --version; go version; semgrep --version'],live)
    command('cweval_compile_c_cpp',['python','cweval/commons.py','compile_all_in','--path','benchmark/core/c','--num_proc','1'],dest)
    command('cweval_compile_cpp',['python','cweval/commons.py','compile_all_in','--path','benchmark/core/cpp','--num_proc','1'],dest)
    command('cweval_compile_go',['python','cweval/commons.py','compile_all_in','--path','benchmark/core/go','--num_proc','1'],dest,timeout=600,env={'GOPROXY':'https://proxy.golang.org,direct'})
    command('cweval_reference_all',['python','-m','pytest','benchmark','-q','-p','no:cacheprovider','--timeout=15','--junitxml=/work/cweval_reference.xml'],dest,timeout=600,env={'PYTHONPATH':str(dest)})
    # SALLM原始不安全实现应能加载且动态测试可执行；失败是预期负对照，不记环境通过率。
    folder=live/'sallm_author'
    if not folder.exists():shutil.copytree(INPUT/'sallm/Dataset/Matching/Author',folder)
    command('sallm_insecure_negative_control',['/opt/sallm/bin/python','-m','pytest','test_A_cwe327_0.py','-q','-p','no:cacheprovider','--junitxml=/work/sallm_negative.xml'],folder)
    folder=live/'codeguard';folder.mkdir(exist_ok=True);candidate=folder/'candidate';candidate.mkdir(exist_ok=True)
    shutil.copy2(INPUT/'codeguard_plus/unit_test/cwe-020/1-py/test_case.py',candidate/'reference.py')
    command('codeguard_functional_reference',['python',str(INPUT/'codeguard_plus/unit_test/cwe-020/1-py/functional.py'),'--path',str(candidate)],folder)
    folder=live/'sec_python'
    if not folder.exists():shutil.copytree(INPUT/'seccodebench_v2/docker/model/python/python_bench/code_injection_eval/workflow_transformer_repo',folder)
    command('seccodebench_python_reference',['python','-m','pytest','tests','-q','-p','no:cacheprovider','--junitxml=/work/sec_python_reference.xml'],folder,env={'PYTHONPATH':str(folder/'src')})
    # 下载的所有Python测试做ast.parse，不执行未选中的样本；语法失败不改变题面verdict。
    integrity=[]
    for p in INPUT.rglob('*.py'):
        if 'test' not in p.name.lower() and '/tests/' not in p.as_posix():continue
        try:ast.parse(p.read_text(encoding='utf-8-sig'));status='syntax_ok'
        except (SyntaxError,UnicodeError) as e:status=type(e).__name__
        integrity.append({'path':p.relative_to(INPUT).as_posix(),'status':status})
    (WORK/'test_syntax_integrity.json').write_text(json.dumps(integrity,indent=2))
    command('python_dependency_lock',['python','-m','pip','freeze'],live)


if __name__=='__main__':main()
