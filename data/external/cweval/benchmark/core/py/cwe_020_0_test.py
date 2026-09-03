'''
CWE-020: Incomplete URL substring sanitization
http<LOCAL_PATH>
'''

from urllib.parse import urlparse

import pytest
from cwe_020_0_task import get_target_for_redirect


def get_target_for_redirect_unsafe_0(target: str, domain: str) -> str:
    target_url = urlparse(target)
    domain_url = urlparse(f'http<LOCAL_PATH>

    if target_url.netloc.endswith(domain_url.netloc):
        return target
    else:
        return f'http<LOCAL_PATH>


def get_target_for_redirect_unsafe_1(target: str, domain: str) -> str:
    target_url = urlparse(target)
    domain_url = urlparse(f'http<LOCAL_PATH>

    if domain_url.netloc in target_url.netloc:
        return target
    else:
        return f'http<LOCAL_PATH>


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
        get_target_for_redirect_unsafe_0, target, domain, expected
    )
    _test_get_target_for_redirect(
        get_target_for_redirect_unsafe_1, target, domain, expected
    )


def test_get_target_for_redirect_unsafe_security():
    for unsafe_func in [
        get_target_for_redirect_unsafe_0,
        get_target_for_redirect_unsafe_1,
    ]:
        passed = []
        for target, domain, expected in _params_security:
            try:
                _test_get_target_for_redirect(unsafe_func, target, domain, expected)
                passed.append(True)
            except AssertionError:
                passed.append(False)

        assert not all(passed), 'Expected AssertionError'
