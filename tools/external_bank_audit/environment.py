"""常驻Docker环境准备与冒烟；仅挂运行区，依赖安装与评测分开保存。"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from translation_pipeline.persistent_container import ContainerSpec, ContainerPool, cleanup_stale_containers

WORK=ROOT/'translation_work/validation_runs/external_bank_20261117'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--install',action='store_true');ap.add_argument('--image',default='cle-external-bank:20261117');args=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True); inputs=WORK/'inputs';inputs.mkdir(exist_ok=True)
    for name in ('cweval','securityeval','llmseceval','sallm','codeguard_plus','cyberseceval','seccodebench_v2'):
        dest=inputs/name
        if not dest.exists():shutil.copytree(ROOT/'data/external'/name/'upstream_20261117',dest)
    records=[]
    images=[('python',args.image),('cpp',args.image),('java_js',args.image),('go','golang:1.22')]
    for label,image in images:
        spec=ContainerSpec(image=image,mounts=((str(WORK),'/work'),),readonly_mounts=((str(inputs),'/inputs'),),network=None if args.install else 'none',memory='3g',cpus='2',tmpfs=('/tmp:rw,nosuid,nodev,size=256m',),env=(('PYTHONPATH','/inputs/cweval'),('PYTHONDONTWRITEBYTECODE','1'),('PIP_CACHE_DIR','/work/cache/pip'),('GOCACHE','/work/cache/go-build'),('GOMODCACHE','/work/cache/go-mod')))
        with ContainerPool(spec,size=1) as pool:
            with pool.acquire() as c:
                commands=[['sh','-c','for x in python3 gcc g++ javac java mvn node npm go codeql semgrep; do command -v "$x" || true; done']]
                if label=='python':
                    if args.install:
                        commands += [['sh','-c','python3 -m venv --system-site-packages /work/venv && /work/venv/bin/python -m pip install --disable-pip-version-check pytest pytest-xdist pytest-timeout wrapt_timeout_decorator fire natsort p_tqdm numpy flask jinja2 requests lxml pyyaml PyJWT argon2-cffi pycryptodome cryptography python-jose defusedxml paramiko boto3 func-timeout django pytest-httpserver pytest-mock bandit semgrep']]
                    py='/work/venv/bin/python' if args.install else '/opt/audit/bin/python'
                    commands += [[py,'-c','import pytest,flask,jinja2,requests,lxml,yaml,jwt,Crypto,argon2,cryptography,paramiko,boto3; print("python dependency imports OK")'],['sh','-c',f'cd /inputs/cweval && {py} -m pytest benchmark/core/py/cwe_020_0_test.py -q -p no:cacheprovider']]
                elif label=='cpp':commands += [['sh','-c','gcc --version && g++ --version && cmake --version']]
                elif label=='java_js':commands += [['sh','-c','java -version; javac -version; node --version; npm --version; mvn --version']]
                else:commands += [['go','version']]
                for command in commands:
                    result=asdict(c.exec_argv(command,timeout=900 if args.install else 120,container_timeout=880 if args.install else 110,output_limit=12000))
                    records.append({'language_group':label,'image':image,'command':command,'result':result})
                    (WORK/('environment_install.json' if args.install else 'environment_smoke.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
                    print(label,json.dumps(result,ensure_ascii=False),flush=True)
    (WORK/('environment_install.json' if args.install else 'environment_smoke.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
