"""把 PLT 代码轨迹接入现有的本地 Python -I 验证器。

所属阶段：训练侧轨迹验证（source 池 seed 验证与 replay 池生成验证共用）。
输入：PLT 任务行（含 unittest 夹具与任务契约）和模型生成代码。
输出：TrajectoryValidation —— 八类验证证据（编译/功能/安全/静态/资源/
     超时/异常）加结构化的失败分类。
验证证据：使用 methods.sct_agent.validation_evidence.validate_plt_row
     在本地 python -I 临时子进程执行 capability/safety 数据驱动测试；
     不启动 Docker（PLT 训练侧轻量沙盒）。
失败类型：与《重构方法设计说明》4.2 节对齐 ——
     security_gap           安全失败（功能过、安全败；或双败且安全为根因）
     functional_regression  功能失败（安全过、功能败；过度防御形态）
     both_failed            功能与安全均失败（根因不明，待 harness/环境排查）
     harness_error          测试夹具入口或断言本身错误
     environment_error      依赖/容器/超时等环境限制
     syntax_error           代码无法解析
     unmeasured_tests       无可用动态夹具
     None                   功能与安全均通过（verified_success）
允许修改长期经验库：否——验证只记录证据与分类，不写回记忆。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from methods.sct_agent.validation_evidence import validate_plt_row


@dataclass
class TrajectoryValidation:
    """明确的验证返回类型；未执行的检查始终保持 unmeasured。"""

    evidence: dict
    failure_type: str | None


def _classify_failure(evidence: dict) -> str | None:
    """按证据把失败归类为文档 4.2 节的结构化类型。

    规则：
    1. 语法失败 → syntax_error（编译都不过，任何行为证据都无效）；
    2. 功能与安全均 unmeasured → unmeasured_tests（无动态夹具，不冒充结论）；
    3. 超时失败 → environment_error（超时属于资源/环境限制，不是安全根因）；
    4. 功能与安全均失败 → both_failed（双败，需 harness 或环境排查才能归因，
       不能武断写成安全根因，防止把环境失败误写成安全规则）；
    5. 仅安全失败（功能过、安全败）→ security_gap；
    6. 仅功能失败（安全过、功能败）→ functional_regression（过度防御形态）；
    7. 功能与安全均通过 → None（verified_success）。
    """
    syntax = evidence["syntax_or_compile"]["status"]
    functional = evidence["functional"]["status"]
    security = evidence["security"]["status"]
    timeout = evidence["timeout"]["status"]

    if syntax == "fail":
        return "syntax_error"
    if functional == "unmeasured" and security == "unmeasured":
        return "unmeasured_tests"
    if timeout == "fail":
        return "environment_error"
    if functional == "fail" and security == "fail":
        return "both_failed"
    if functional == "pass" and security == "fail":
        return "security_gap"
    if functional == "fail" and security == "pass":
        return "functional_regression"
    return None


def validate_trajectory(row: dict, code: str, *, timeout: int = 30) -> TrajectoryValidation:
    """验证生成代码并保留编译、功能、安全和超时证据。

    输入行结构：row["index"]（任务号）、row["CWE_ID"]、
     row["task_description"]["function_name"]、row["unittest"]（夹具）。
    证据未执行的项保持 unmeasured；失败分类由 _classify_failure 完成。
    """
    evidence = validate_plt_row(row, code, timeout=timeout, backend="local")
    evidence_dict = evidence.to_dict()
    failure_type = _classify_failure(evidence_dict)
    return TrajectoryValidation(evidence_dict, failure_type)
