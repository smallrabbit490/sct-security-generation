"""公开修复选择：只比较同一公开用例集和公开静态契约，不读取正式 F/S/Joint。

本模块位于生成 c1 之后、正式评分之前；不调用模型、不执行候选、不写长期库。
指纹绑定只能记录调用者实际传入执行器的代码和 suite，不能认证旧日志的来源，
也不能证明模型生成的公开断言语义正确。PLT/Base/Plus 的最终测试不属于输入。
"""
from __future__ import annotations

import ast
import hashlib
import json
from typing import Any


POLICY_VERSION = "public_repair_policy.v1"
_RESULT_SOURCE = "self_generated_internal"
_CONTRACT_SOURCE = "public_contract_static"
_CONTRACT_VERSION = "public_contract_checks.v1"
_MEASURED_STATUSES = {"pass", "fail", "runtime_error", "syntax_error", "timeout"}
_CASE_FIELDS = ("id", "kind", "purpose", "status", "measured", "phase", "error")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fixed_cases(suite: dict) -> list[dict]:
    cases = suite.get("cases") if isinstance(suite, dict) else None
    if not isinstance(cases, list) or len(cases) > 6:
        raise ValueError("invalid_public_suite")
    output = []
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid_public_case")
        if any(not isinstance(case.get(key), str) or not case[key].strip()
               for key in ("id", "kind", "purpose", "code")):
            raise ValueError("invalid_public_case")
        if case["kind"] not in ("functional", "security") or case["id"] in seen:
            raise ValueError("invalid_or_duplicate_public_case")
        seen.add(case["id"])
        output.append({key: case[key] for key in ("id", "kind", "purpose", "code")})
    return output


def suite_fingerprint(suite: dict) -> str:
    """修复前冻结公开 suite 的逐例内容与顺序；结构无效时失败，不读取隐藏材料。"""
    serialized = json.dumps(_fixed_cases(suite), sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"))
    return _digest(serialized)


def bind_public_result(code: str, suite: dict, result: dict) -> dict:
    """公开执行后立刻绑定代码和固定 suite，并只保留公开执行字段。

    调用者必须刚刚以这些输入执行 execute_checks；此函数不运行代码、不把
    历史结果重新认证为新政策成绩。非法 suite/代码类型抛错；不写长期经验库。
    """
    if not isinstance(code, str) or not isinstance(result, dict):
        raise ValueError("invalid_public_result_binding_input")
    binding = {
        "schema_version": POLICY_VERSION,
        "code_sha256": _digest(code),
        "suite_sha256": suite_fingerprint(suite),
    }
    if "public_binding" in result and result["public_binding"] != binding:
        raise ValueError("cannot_rebind_public_result_to_different_input")
    rows = result.get("cases", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid_public_result_cases")
    public_rows = [
        {key: row[key] for key in _CASE_FIELDS if key in row}
        for row in rows
    ]
    return {
        "source": result.get("source"),
        "backend": result.get("backend"),
        "public_binding": binding,
        "measured": any(row.get("measured") is True for row in public_rows),
        "measured_count": sum(row.get("measured") is True for row in public_rows),
        "passed": sum(row.get("measured") is True and row.get("status") == "pass"
                      for row in public_rows),
        "cases": public_rows,
    }


def _syntax_state(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        return "empty"
    try:
        parsed = ast.parse(code)
        if not parsed.body:
            return "empty"
        compile(parsed, "<public_repair_candidate>", "exec")
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return "invalid"
    return "valid"


def _case_index(code: str, suite: dict, result: dict) -> dict[str, dict]:
    if not isinstance(result, dict) or result.get("source") != _RESULT_SOURCE:
        raise ValueError("not_public_internal_result")
    expected_binding = {
        "schema_version": POLICY_VERSION,
        "code_sha256": _digest(code),
        "suite_sha256": suite_fingerprint(suite),
    }
    if result.get("public_binding") != expected_binding:
        raise ValueError("public_result_binding_mismatch")
    if result.get("backend") not in ("local", "docker"):
        raise ValueError("unknown_public_execution_backend")
    expected = {case["id"]: case for case in _fixed_cases(suite)}
    rows = result.get("cases")
    if not isinstance(rows, list):
        raise ValueError("invalid_public_case_results")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("invalid_public_case_result")
        case_id = row["id"]
        if case_id not in expected or case_id in indexed:
            raise ValueError("unexpected_or_duplicate_public_case_result")
        case = expected[case_id]
        if row.get("kind") != case["kind"] or row.get("purpose") != case["purpose"]:
            raise ValueError("public_case_contract_mismatch")
        if row.get("measured") is not True or row.get("status") not in _MEASURED_STATUSES:
            raise ValueError("public_case_unmeasured")
        indexed[case_id] = row
    if indexed.keys() != expected.keys():
        raise ValueError("missing_public_case_result")
    return indexed


def _contract_index(result: dict) -> dict[str, dict]:
    if not isinstance(result, dict) or result.get("source") != _CONTRACT_SOURCE:
        raise ValueError("not_public_contract_result")
    if result.get("schema_version") != _CONTRACT_VERSION or result.get("measured") is not True:
        raise ValueError("public_contract_unmeasured")
    check_ids = result.get("check_ids")
    if (not isinstance(result.get("contract_digest"), str) or not result["contract_digest"]
            or not isinstance(check_ids, list) or not check_ids
            or any(not isinstance(value, str) or not value for value in check_ids)
            or len(check_ids) != len(set(check_ids))):
        raise ValueError("invalid_public_contract_scope")
    coverage = {}
    for key in ("measured_check_ids", "unmeasured_check_ids"):
        values = result.get(key)
        if (not isinstance(values, list)
                or any(not isinstance(value, str) or not value for value in values)
                or len(values) != len(set(values))):
            raise ValueError("invalid_public_contract_measurement_scope")
        coverage[key] = set(values)
    measured_ids = coverage["measured_check_ids"]
    unmeasured_ids = coverage["unmeasured_check_ids"]
    if (measured_ids & unmeasured_ids
            or measured_ids | unmeasured_ids != set(check_ids)):
        raise ValueError("invalid_public_contract_measurement_scope")
    violations = result.get("violations")
    if not isinstance(violations, list):
        raise ValueError("invalid_public_contract_violations")
    indexed = {}
    for violation in violations:
        if not isinstance(violation, dict) or not isinstance(violation.get("id"), str):
            raise ValueError("invalid_public_contract_violation")
        violation_id = violation["id"]
        if not violation_id or violation_id in indexed:
            raise ValueError("duplicate_public_contract_violation")
        if violation_id not in measured_ids:
            raise ValueError("public_contract_violation_not_measured")
        indexed[violation_id] = violation
    expected_status = "fail" if indexed else "pass"
    if result.get("status") != expected_status:
        raise ValueError("inconsistent_public_contract_status")
    return indexed


def repair_opportunity(code: str, suite: dict, internal: dict, contract_checks: dict) -> dict:
    """c0 公开测量后决定是否值得生成 c1；只识别现有选择规则允许的改善机会。

    空 suite、缺测、无效绑定/静态范围均不生成修复；语法有效且所有公开例已通过、
    无静态违规时也不生成。其余完整公开失败可尝试一次修复，但不保证 c1 被接受。
    不调用模型或验证器，不接触正式 F/S/Joint，不更新长期经验库。
    """
    opportunity = {"should_generate_repair": False, "reason": "no_strict_public_improvement_possible"}
    try:
        if not _fixed_cases(suite):
            raise ValueError("empty_public_suite")
        rows = _case_index(code, suite, internal)
        violations = _contract_index(contract_checks)
    except (ValueError, TypeError) as error:
        opportunity["reason"] = str(error)
        return opportunity
    syntax = _syntax_state(code)
    has_failed_case = any(row["status"] != "pass" for row in rows.values())
    if syntax == "valid" and not has_failed_case and not violations:
        return opportunity
    if syntax != "valid":
        reason = "syntax_recovery_opportunity"
    elif has_failed_case:
        reason = "public_case_repair_opportunity"
    else:
        reason = "public_contract_repair_opportunity"
    return {"should_generate_repair": True, "reason": reason}


def choose_public_candidate(*, original_code: str, repaired_code: str, suite: dict,
                            original_internal: dict, repaired_internal: dict,
                            original_contract: dict, repaired_contract: dict) -> dict:
    """c1 生成后的公开逐例保守选择；输出选择与原因，不接受正式评分输入。

    两边必须绑定同一非空 suite、同一后端，并完成全部公开用例和同范围静态
    检查。c1 必须覆盖 c0 所有已测静态规则，未知不能充当已修复；语法恢复允许
    新增已测规则。c1 必须保留 c0 全部通过例、不新增硬契约违规，且修好至少一例或
    一项公开硬违规。空集、缺测、不可比、无严格改善均保留 c0；不能用通过数
    增长抵消逐例回归。c0 空/语法失败恢复另要求 c1 静态无违规且至少一例通过。
    这些条件仅支持公开证据改善，不证明正式 Function、Secure 或 Joint 改善。
    """
    original_syntax = _syntax_state(original_code)
    repaired_syntax = _syntax_state(repaired_code)
    decision = {
        "schema_version": POLICY_VERSION,
        "source": "public_checks_only",
        "selected_attempt": 0,
        "reason": "no_strict_public_improvement",
        "comparable": False,
        "original_syntax": original_syntax,
        "repaired_syntax": repaired_syntax,
        "improved_case_ids": [],
        "regressed_case_ids": [],
        "removed_contract_violation_ids": [],
        "new_contract_violation_ids": [],
        "lost_measured_contract_check_ids": [],
        "newly_measured_contract_check_ids": [],
        "formal_metrics": "unmeasured",
    }
    if repaired_syntax != "valid":
        decision["reason"] = "repair_empty_or_syntax_invalid"
        return decision
    if original_code == repaired_code:
        decision["reason"] = "unchanged_code"
        return decision
    try:
        cases = _fixed_cases(suite)
        decision["suite_sha256"] = suite_fingerprint(suite)
        if not cases:
            raise ValueError("empty_public_suite")
        original_rows = _case_index(original_code, suite, original_internal)
        repaired_rows = _case_index(repaired_code, suite, repaired_internal)
        if original_internal["backend"] != repaired_internal["backend"]:
            raise ValueError("public_execution_backend_mismatch")
        original_violations = _contract_index(original_contract)
        repaired_violations = _contract_index(repaired_contract)
        if (original_contract["contract_digest"] != repaired_contract["contract_digest"]
                or set(original_contract["check_ids"]) != set(repaired_contract["check_ids"])):
            raise ValueError("public_contract_scope_mismatch")
        original_measured = set(original_contract["measured_check_ids"])
        repaired_measured = set(repaired_contract["measured_check_ids"])
        decision["lost_measured_contract_check_ids"] = sorted(original_measured - repaired_measured)
        decision["newly_measured_contract_check_ids"] = sorted(repaired_measured - original_measured)
        if decision["lost_measured_contract_check_ids"]:
            raise ValueError("public_contract_measurement_regression")
    except (ValueError, TypeError) as error:
        decision["reason"] = str(error)
        return decision

    original_passes = {key for key, row in original_rows.items() if row["status"] == "pass"}
    repaired_passes = {key for key, row in repaired_rows.items() if row["status"] == "pass"}
    improved = sorted(repaired_passes - original_passes)
    regressed = sorted(original_passes - repaired_passes)
    removed = sorted(original_violations.keys() - repaired_violations.keys())
    added = sorted(repaired_violations.keys() - original_violations.keys())
    decision.update(comparable=True, improved_case_ids=improved, regressed_case_ids=regressed,
                    removed_contract_violation_ids=removed, new_contract_violation_ids=added)
    if added:
        decision["reason"] = "new_public_contract_violation"
    elif regressed:
        decision["reason"] = "public_case_regression"
    elif original_syntax != "valid":
        if repaired_violations or not improved:
            decision["reason"] = "syntax_recovery_without_clean_public_evidence"
        else:
            decision.update(selected_attempt=1, reason="syntax_recovery_with_public_improvement")
    elif improved or removed:
        reason = "public_case_improvement" if improved else "public_contract_improvement"
        if improved and removed:
            reason = "public_case_and_contract_improvement"
        decision.update(selected_attempt=1, reason=reason)
    return decision


def public_repair_feedback(suite: dict, internal: dict, contract_checks: dict) -> dict:
    """c0 修复输入只回流固定公开用例、实际错误和公开静态违规的白名单。

    公开用例正文来自 suite，不能由结果行替换；正式 validation/F/S/Joint 等
    额外字段一律忽略。缺测保留缺测，指纹或来源错误不给实际错误回流。
    不运行测试、不宣称人工审查、独立审核或隐藏测试结论，不修改长期库。
    """
    cases = _fixed_cases(suite)
    fingerprint = suite_fingerprint(suite)
    source_ok = (isinstance(internal, dict) and internal.get("source") == _RESULT_SOURCE
                 and isinstance(internal.get("public_binding"), dict)
                 and internal["public_binding"].get("schema_version") == POLICY_VERSION
                 and internal["public_binding"].get("suite_sha256") == fingerprint)
    indexed: dict[str, list[dict]] = {}
    if source_ok and isinstance(internal.get("cases"), list):
        for row in internal["cases"]:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                indexed.setdefault(row["id"], []).append(row)
    public_rows = []
    for case in cases:
        rows = indexed.get(case["id"], [])
        row = rows[0] if len(rows) == 1 else {}
        status = row.get("status", "unmeasured")
        measured = row.get("measured") is True and status in _MEASURED_STATUSES
        public_row = {**case, "status": status if isinstance(status, str) else "unmeasured",
                      "measured": measured}
        for key in ("phase", "error"):
            if isinstance(row.get(key), str):
                public_row[key] = row[key]
        public_rows.append(public_row)

    # 静态结果的来源不符时，不转发其中可能属于正式验证器的错误正文。
    contract_public: dict[str, Any] = {
        "source": _CONTRACT_SOURCE, "measured": False, "status": "unmeasured", "violations": []}
    if (isinstance(contract_checks, dict) and contract_checks.get("source") == _CONTRACT_SOURCE
            and contract_checks.get("schema_version") == _CONTRACT_VERSION):
        for key in ("schema_version", "status", "contract_digest"):
            if isinstance(contract_checks.get(key), str):
                contract_public[key] = contract_checks[key]
        contract_public["measured"] = contract_checks.get("measured") is True
        for key in ("check_ids", "measured_check_ids", "unmeasured_check_ids", "unmeasured"):
            if isinstance(contract_checks.get(key), list):
                contract_public[key] = [item for item in contract_checks[key] if isinstance(item, str)]
        violations = contract_checks.get("violations", [])
        contract_public["violations"] = [
            {key: item[key] for key in ("id", "rule_id", "symbol", "line", "message", "public_source")
             if key in item and isinstance(item[key], (str, int))}
            for item in (violations if isinstance(violations, list) else []) if isinstance(item, dict)
        ]
    return {
        "source": "public_checks_only",
        "internal_checks": {
            "source": _RESULT_SOURCE, "suite_sha256": fingerprint,
            "measured": any(row["measured"] for row in public_rows),
            "measured_count": sum(row["measured"] for row in public_rows),
            "passed": sum(row["measured"] and row["status"] == "pass" for row in public_rows),
            "cases": public_rows,
        },
        "public_contract_checks": contract_public,
    }
