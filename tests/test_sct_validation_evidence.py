from methods.sct_agent.validation_evidence import validate_generated_code
from methods.sct_agent.validation_evidence import validate_plt_row


def test_validator_preserves_function_security_and_unmeasured_states():
    evidence = validate_generated_code(
        "python",
        "def f(): return 1",
        functional=lambda code: True,
        security=lambda code: False,
    )
    assert evidence.functional.status == "pass"
    assert evidence.security.status == "fail"
    assert evidence.static_analysis.status == "unmeasured"


def test_plt_dynamic_check_uses_local_backend_without_docker():
    row = {
        "index": 7,
        "task_description": {"function_name": "add_one"},
        "unittest": {"testcases": "def check(candidate):\n    assert candidate(1) == 2\n"},
    }
    evidence = validate_plt_row(row, "def add_one(value):\n    return value + 1\n", backend="local")
    assert evidence.metadata["backend"] == "local"
    assert evidence.functional.status == "pass"
    assert evidence.security.status == "pass"


def test_plt_data_driven_testcases_execute_capability_and_safety_groups():
    """SeCodePLT 原生 testcases=... 模板应分别执行功能组和安全组。"""
    row = {
        "index": 8,
        "task_description": {"function_name": "normalize_name"},
        "unittest": {
            "setup": "import builtins",
            "testcases": """
testcases = {
    "capability": [
        ({"name": " Alice "}, "Alice"),
    ],
    "safety": [
        ({"name": ""}, ValueError),
    ],
}
""",
        },
    }
    code = """
def normalize_name(name):
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    return name
"""
    evidence = validate_plt_row(row, code, backend="local", timeout=5)
    assert evidence.metadata["dynamic_test"] == "executed"
    assert evidence.metadata["test_format"] == "secodeplt_data_driven"
    assert evidence.functional.status == "pass"
    assert evidence.security.status == "pass"


def test_plt_data_driven_failure_is_not_marked_unmeasured():
    """可执行用例失败时必须记录 fail，而不是退化成 unmeasured。"""
    row = {
        "index": 9,
        "task_description": {"function_name": "identity"},
        "unittest": {
            "setup": "",
            "testcases": "testcases = {'capability': [({'value': 1}, 2)], 'safety': []}",
        },
    }
    evidence = validate_plt_row(row, "def identity(value):\n    return value\n", backend="local", timeout=5)
    assert evidence.metadata["dynamic_test"] == "executed"
    assert evidence.functional.status == "fail"
    assert evidence.functional.error_type == "plt_test_failed"
    assert evidence.security.status == "unmeasured"
