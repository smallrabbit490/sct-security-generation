"""本地 PLT 子进程只继承运行必需白名单，Windows socket 不依赖遗失的系统路径。"""
import os
import subprocess

import pytest

from methods.sct_agent import validation_evidence as ve
from methods.sct_trajectory.global_gate import evidence_is_measured


@pytest.mark.skipif(os.name != "nt", reason="Windows Winsock depends on SYSTEMROOT")
@pytest.mark.parametrize("executor", ["legacy", "data_driven"])
def test_local_validators_support_socket_initialization_without_network(executor):
    code = "import socket\ndef f():\n    s = socket.socket()\n    s.close()\n    return True\n"
    if executor == "legacy":
        functional, security, timeout = ve._run_local_plt_check(code, "f", "def check(candidate):\n    assert candidate() is True", 15)
    else:
        functional, security, timeout, _ = ve._run_local_plt_data_driven(code, "f", "",
            'testcases = {"capability": [({}, True)], "safety": [({}, True)]}', 15)
    assert functional.status == "pass", functional.to_dict()
    assert security.status == "pass", security.to_dict()


@pytest.mark.parametrize("executor", ["legacy", "data_driven"])
def test_subprocess_environment_remains_allowlisted(monkeypatch, executor):
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-not-a-real-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sentinel-not-a-real-key")
    monkeypatch.setenv("PYTHONPATH", "sentinel-untrusted-pythonpath")
    seen = []
    original_run = subprocess.run
    def run(*args, **kwargs):
        seen.append(dict(kwargs["env"]))
        return original_run(*args, **kwargs)
    monkeypatch.setattr(ve.subprocess, "run", run)
    code = "def f(): return True"
    if executor == "legacy":
        ve._run_local_plt_check(code, "f", "def check(candidate): assert candidate()", 15)
    else:
        ve._run_local_plt_data_driven(code, "f", "", 'testcases = {"capability": [({}, True)], "safety": [({}, True)]}', 15)
    assert len(seen) == 1
    assert set(seen[0]) <= {"PATH", "PYTHONIOENCODING", "SYSTEMROOT"}
    assert all(key not in seen[0] for key in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "PYTHONPATH"))
    if os.name == "nt":
        assert seen[0]["SYSTEMROOT"] == os.environ["SYSTEMROOT"]


def validated(code, setup="", tests=None):
    row = {"index": 1, "task_description": {"function_name": "f"}, "unittest": {
        "setup": setup, "testcases": tests or 'testcases = {"capability": [({}, True)], "safety": [({}, True)]}'}}
    return ve.validate_plt_row(row, code, timeout=15).to_dict()


@pytest.mark.parametrize("code,error", [
    ("import nonexistent_sct_review_package\ndef f(): return True", "candidate_import_error"),
    ("def other(): return True", "candidate_execution_error"),
    ("raise OSError('candidate rejected path')\ndef f(): return True", "candidate_execution_error"),
])
def test_candidate_top_level_errors_are_measured_not_validator_incidents(code, error):
    evidence = validated(code)
    assert evidence["functional"]["error_type"] == error
    assert evidence["security"]["error_type"] == error
    assert evidence_is_measured(evidence)
    assert evidence["metadata"]["worker_error"]["stage"] == "candidate"


@pytest.mark.parametrize("setup,tests,stage", [
    ("raise RuntimeError('fixture setup failed')", None, "setup"),
    ("", 'raise RuntimeError("fixture definition failed")\ntestcases = {"capability": [], "safety": []}', "test_definition"),
])
def test_fixture_errors_remain_unmeasured(setup, tests, stage):
    evidence = validated("def f(): return True", setup, tests)
    assert evidence["functional"]["error_type"] == "plt_validator_exception"
    assert not evidence_is_measured(evidence)
    assert evidence["metadata"]["worker_error"]["stage"] == stage


def test_confirmed_winsock_environment_error_remains_unmeasured():
    code = "error = OSError('winsock unavailable')\nerror.winerror = 10106\nraise error\ndef f(): return True"
    evidence = validated(code)
    assert evidence["functional"]["error_type"] == "environment_error"
    assert not evidence_is_measured(evidence)
    assert evidence["metadata"]["worker_error"]["winerror"] == 10106


def test_winsock_environment_error_during_test_call_is_not_model_failure():
    code = "def f():\n    error = OSError('winsock unavailable')\n    error.winerror = 10106\n    raise error"
    evidence = validated(code)
    assert evidence["functional"]["error_type"] == "environment_error"
    assert not evidence_is_measured(evidence)
    assert evidence["metadata"]["worker_error"]["stage"] == "test_execution"
