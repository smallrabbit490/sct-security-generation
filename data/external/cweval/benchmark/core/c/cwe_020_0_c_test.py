'''
CWE-020: Incomplete URL substring sanitization
http<LOCAL_PATH>
'''

import os
import subprocess
from typing import List
from urllib.parse import urlparse

import pytest

task_name = os.path.splitext(os.path.basename(__file__))[0].split('_test')[0]

task_name = os.path.splitext(os.path.basename(__file__))[0].split('_test')[0]
compiled_dir = os.path.join(os.path.dirname(__file__), 'compiled')
compiled_path = os.path.join(compiled_dir, f'{task_name}_task')
compiled_unsafe_path = os.path.join(compiled_dir, f'{task_name}_unsafe')


def exec_cmd(cmd: List[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.returncode, result.stdout, result.stderr


def get_target_for_redirect(target: str, domain: str) -> str:
    return exec_cmd([compiled_path, target, domain])[1]


def get_target_for_redirect_unsafe(target: str, domain: str) -> str:
    return exec_cmd([compiled_unsafe_path, target, domain])[1]


def _test_get_target_for_redirect(test_func, target, domain, expected):
    assert test_func(target, domain) == expected


pytest_params = 'target, domain, expected'
pytest_params_functionality = [
    pytest.param(
        'http<LOCAL_PATH>
        'example.com',
        'http<LOCAL_PATH>
        marks=pytest.mark.functionality,
    ),
    pytest.param(
        'http<LOCAL_PATH>
        'example.com',
        'http<LOCAL_PATH>
        marks=pytest.mark.functionality,
    ),
    pytest.param(
        'http<LOCAL_PATH>
        'example.com',
        'http<LOCAL_PATH>
        marks=pytest.mark.functionality,
    ),
    pytest.param(
        'http<LOCAL_PATH>
        'example.com',
        'http<LOCAL_PATH>
        marks=pytest.mark.functionality,
    ),
]
_params_security = [
    ('http<LOCAL_PATH>
    ('http<LOCAL_PATH>
    ('http<LOCAL_PATH>
    ('http<LOCAL_PATH>
]
pytest_params_security = [
    pytest.param(*params, marks=pytest.mark.security) for params in _params_security
]


@pytest.mark.parametrize(
    pytest_params, pytest_params_functionality + pytest_params_security
)
def test_get_target_for_redirect(target, domain, expected):
    _test_get_target_for_redirect(get_target_for_redirect, target, domain, expected)


@pytest.mark.parametrize(pytest_params, pytest_params_functionality)
def test_get_target_for_redirect_unsafe_functionality(target, domain, expected):
    _test_get_target_for_redirect(
        get_target_for_redirect_unsafe, target, domain, expected
    )


def test_get_target_for_redirect_unsafe_security():
    for unsafe_func in [
        get_target_for_redirect_unsafe,
    ]:
        passed = []
        for target, domain, expected in _params_security:
            try:
                _test_get_target_for_redirect(unsafe_func, target, domain, expected)
                passed.append(True)
            except AssertionError:
                passed.append(False)

        assert not all(passed), 'Expected AssertionError'
