"""在单个常驻容器中运行验证检查，构建完成后才开始watchdog监测。"""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from translation_pipeline.persistent_container import ContainerSpec,ContainerPool

def main():
    work=ROOT/'translation_work/validation_runs/external_bank_20261117'
    shutil.copy2(Path(__file__).with_name('docker_checks.py'),work/'docker_checks.py')
    spec=ContainerSpec(image='cle-external-bank:20261117',mounts=((str(work),'/work'),),readonly_mounts=((str(work/'inputs'),'/inputs'),),network=None,memory='4g',cpus='2',tmpfs=('/tmp:rw,nosuid,nodev,size=512m',),env=(('PYTHONDONTWRITEBYTECODE','1'),('GOCACHE','/work/cache/go-build'),('GOMODCACHE','/work/cache/go-mod'),('MAVEN_OPTS','-Dmaven.repo.local=/work/cache/m2')))
    with ContainerPool(spec,size=1) as pool:
        with pool.acquire() as c:
            r=asdict(c.exec_argv(['python','/work/docker_checks.py'],timeout=2000,container_timeout=1980,output_limit=10000))
            (work/'docker_checks_execution.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(r,ensure_ascii=False))

if __name__=='__main__':main()
