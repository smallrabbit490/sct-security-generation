"""新候选数据的常驻 Docker 冒烟；分别保留编译、功能、安全结果，不派发模型。"""
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from translation_pipeline.persistent_container import ContainerPool, ContainerSpec, cleanup_stale_containers


def main():
    work = ROOT / 'translation_work/validation_runs/candidates_20261118'
    cleanup_stale_containers()
    spec = ContainerSpec(image='cle-candidates:20261118', mounts=((str(work), '/work'), (str(ROOT / 'translation_work/downloads/codeql/query-source'), '/opt/codeql-query-source')), readonly_mounts=((str(work / 'inputs'), '/inputs'),), env=(('MAVEN_OPTS', '-Djansi.tmpdir=/work/jansi'),), network='none', memory='4g', cpus='2', tmpfs=('/tmp:rw,nosuid,nodev,size=512m',))
    records = []
    commands = [('toolchain', 'mkdir -p /work/jansi && python --version && gcc --version && g++ --version && java -version && node --version && go version && mvn --version && ruby --version && codeql version')]
    commands.append(('pythonsecurityeval/handwritten_control', 'cd /work/cases/pythonsecurityeval/1 && python unit_test.py'))
    commands.append(('codeql/query_resolution', 'codeql resolve qlpacks --search-path=/opt/codeql-query-source/github-codeql-e637eb7'))
    commands.append(('codeql/python_database', 'codeql database create /work/codeql-control/db --language=python --source-root=/work/codeql-control/source --overwrite && codeql database analyze /work/codeql-control/db /opt/codeql-query-source/github-codeql-e637eb7/python/ql/src/Security/CWE-078/CommandInjection.ql --search-path=/opt/codeql-query-source/github-codeql-e637eb7 --format=csv --output=/work/codeql-control/alerts.csv --ram=2048 --threads=2'))
    commands.append(('codelmsec/query_control', 'cp /inputs/codeql_codelmsec/codql_qls_codelmsec/python/ql/src/Security/CWE-078/CommandInjection.ql /opt/codeql-query-source/github-codeql-e637eb7/python/ql/src/Security/CWE-078/CodeLMSecCommandInjection.ql && codeql database analyze /work/codeql-control/db /opt/codeql-query-source/github-codeql-e637eb7/python/ql/src/Security/CWE-078/CodeLMSecCommandInjection.ql --search-path=/opt/codeql-query-source/github-codeql-e637eb7 --format=csv --output=/work/codeql-control/codelmsec-alerts.csv --ram=2048 --threads=2'))
    for language in ('python', 'c', 'cpp', 'java'):
        for kind in ('functional', 'security'):
            path = work / 'cases/autosuit' / language / kind
            meta = json.loads((path / 'metadata.json').read_text())
            prefix = f'cd /work/cases/autosuit/{language}/{kind} && '
            if language == 'python':
                command = f'python -m pytest {meta["test"]} -q -p no:cacheprovider'
            elif language in ('c', 'cpp'):
                compiler = 'gcc' if language == 'c' else 'g++'
                command = f'{compiler} -DUNIT_TEST {meta["test"]} -o test_bin && ./test_bin'
            else:
                cp = '/inputs/java/*:/inputs/java/lib/*'
                command = f'javac -encoding UTF-8 -cp "{cp}" *.java && java -cp ".:/inputs/java/*:/inputs/java/lib/*" org.junit.platform.console.ConsoleLauncher --scan-class-path --reports-dir reports'
            commands.append((f'autosuit/{language}/{kind}/{meta["id"]}', prefix + command))
    with ContainerPool(spec, size=1) as pool:
        with pool.acquire() as container:
            for label, command in commands:
                result = asdict(container.exec_argv(['sh', '-c', command], timeout=600 if label.startswith(('codeql/', 'codelmsec/')) else 180, container_timeout=580 if label.startswith(('codeql/', 'codelmsec/')) else 170, output_limit=10000))
                records.append({'label': label, 'command': command, 'result': result})
                (work / 'smoke_results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
                print(label, json.dumps(result, ensure_ascii=False), flush=True)
    # 独立 oracle 冒烟：不运行 agent，参考解和隐藏测试仅在验证容器中汇合。
    lsc_spec = ContainerSpec(image='cle-lscbench-verifier:cve-2024-5751', mounts=((str(work), '/work'),), readonly_mounts=((str(work / 'inputs'), '/inputs'),), env=(('MAVEN_OPTS', '-Djansi.tmpdir=/work/jansi'),), network='none', memory='4g', cpus='2', tmpfs=('/tmp:rw,nosuid,nodev,size=512m',))
    with ContainerPool(lsc_spec, size=1) as pool:
        with pool.acquire() as container:
            command = 'mkdir -p /work/lscbench/logs /work/lscbench/tests && cp -a /tests/. /work/lscbench/tests/ && rm -rf /tests && ln -s /work/lscbench/tests /tests && mkdir -p /logs && ln -s /work/lscbench/logs /logs/verifier && bash /inputs/lscbench/solution/solve.sh && bash /tests/test.sh; cat /logs/verifier/reward.json'
            result = asdict(container.exec_argv(['bash', '-c', command], timeout=600, container_timeout=580, output_limit=16000))
            records.append({'label': 'lscbench/oracle/cve-2024-5751_function', 'command': command, 'result': result})
            (work / 'smoke_results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
            print('lscbench/oracle', json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
