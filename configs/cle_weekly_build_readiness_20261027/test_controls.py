"""只测本次准备必需的进程识别、独占锁及回放比较修复。"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from configs.cle_weekly_build_20261027.process_guard import exclusive_slots
from configs.cle_weekly_build_readiness_20261027.runtime import MODULE, active_workers
from configs.cle_weekly_build_readiness_20261027.compare import stable, digest
from configs.cle_weekly_build_readiness_20261027 import execute


def test_cim_instances_arbitrary_embedding_task_and_self():
    processes = [
        {'ProcessId': 1, 'ParentProcessId': 0, 'CommandLine': 'python -m configs.cle_weekly_proxy_recovery_20261027.runner run --kind q'},
        {'ProcessId': 2, 'ParentProcessId': 1, 'CommandLine': 'python -m configs.cle_weekly_proxy_recovery_20261027.runner run --kind q'},
        {'ProcessId': 3, 'ParentProcessId': 0, 'CommandLine': 'python -m configs.cle_weekly_embedding_recovery_20261027.resume run 9876'},
        {'ProcessId': 4, 'ParentProcessId': 3, 'CommandLine': 'python -m configs.cle_weekly_embedding_recovery_20261027.resume run 9876'},
        {'ProcessId': 5, 'ParentProcessId': 0, 'CommandLine': 'python -m ' + MODULE + ' run'},
        {'ProcessId': 6, 'ParentProcessId': 5, 'CommandLine': 'python -m ' + MODULE + ' run'},
        {'ProcessId': 7, 'ParentProcessId': 0, 'CommandLine': 'python -m tools.task_custom run'},
    ]
    actual = active_workers(processes, own_pid=6, registered=[
        {'pid': 7, 'package': 'FR', 'command_marker': 'tools.task_custom'}])
    assert [(p['ProcessId'], p['package']) for p in actual] == [(2, 'FQ_LEARN'), (4, 'FFS'), (7, 'FR')]


@pytest.mark.parametrize('package', ['learning', 'FQ_RETEST', 'FQ_GATE', 'FFS', 'FG_LABELS', 'FG_GATE', 'FR'])
def test_exclusive_four_slots_block_every_other_package(tmp_path, package):
    relative = 'learning.lock' if package == 'learning' else package + '/execution.lock'
    child = """import msvcrt, sys
from pathlib import Path
p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True)
with p.open('a+b') as f:
 if f.tell()==0: f.write(b'0'); f.flush()
 f.seek(0)
 try:
  msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  print('acquired')
 except OSError: print('blocked')
"""
    with exclusive_slots(tmp_path):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', child, str(tmp_path / relative)],
                                capture_output=True, text=True, check=True)
        assert result.stdout.strip() == 'blocked'
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', child, str(tmp_path / relative)],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'acquired'


def test_compare_excludes_only_timing_and_preserves_content():
    a = {'invariant_id': 'a', 'positive_principle': 'Preserve valid input.',
         'retrieval_audit': {'selector_attempts': [{'elapsed_seconds': 1, 'content_sha256': 'same'}]}}
    b = json.loads(json.dumps(a))
    b['retrieval_audit']['selector_attempts'][0]['elapsed_seconds'] = 2
    assert stable({'card': a, 'sha256': digest(a)}) == stable({'card': b, 'sha256': digest(b)})
    b['positive_principle'] = 'Different advice.'
    assert stable(a) != stable(b)
    with pytest.raises(ValueError, match='digest_mismatch'):
        stable({'card': a, 'sha256': 'wrong'})


def test_check_requires_unchanged_finite_budget(monkeypatch):
    budget = {'budget_proposed': {'conservative_model_and_embedding_tokens': 560398731,
              'total_physical_HTTP_attempts': 97377,
              'embedding_HTTP_attempts_included_in_total': 36792},
              'execution_ready': True, 'reset_on_resume': False}
    monkeypatch.setattr(execute.original, 'check', lambda: {'ready': True, 'missing': [], 'API_calls': 0})
    monkeypatch.setattr(execute.original, 'read', lambda p: budget)
    monkeypatch.setattr(execute, 'active_workers', lambda: [])
    assert execute.check()['ready']
    budget['budget_proposed']['total_physical_HTTP_attempts'] += 1
    assert not execute.check()['ready']


def test_hash_seed_stable_in_two_processes():
    command = [sys.executable, '-B', '-c', "print(hash('conditional native experience'))"]
    values = [subprocess.run(command, capture_output=True, text=True, check=True,
                             env={**os.environ, 'PYTHONHASHSEED': '20261027'}).stdout for _ in range(2)]
    assert values[0] == values[1]
