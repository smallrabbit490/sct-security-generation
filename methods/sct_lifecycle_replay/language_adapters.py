"""多语言验证接口：原则共享，Python/Go/C++ 的编译与 harness 由适配器注入。

所属阶段：多语言安全经验架构（文档 9 节）与冻结评测前的语言适配层。
设计：两层架构 —— 语言无关安全原则（经验卡的 principle）+ 目标语言
     API/类型/异常适配（LanguageAdapter）。这样能区分「原则没学会」
     与「原则学会了但语言实现错误」，把跨语言迁移变成可测量的实验因素。
当前实现：Python 适配器接入本地 PLT 验证（ast 语法 + capability/safety
     数据驱动测试）；Go/C++ 适配器声明 backend=docker_harness 但验证回调
     未注入时为 unmeasured —— 未执行的验证项必须记录为未测量，不能默认为通过。
允许修改长期经验库：否——适配器只执行验证并返回证据，不写回记忆。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class LanguageAdapter:
    """目标语言适配边界，不把一种语言的 API 当作通用答案。

    字段是验证回调契约：compile_or_syntax / functional / security 分别
    接收生成代码并返回证据 dict（含 status/details/error_type）。
    未注入的回调由 validate() 统一记为 unmeasured。
    """

    language: str
    compile_or_syntax: Callable[[str], dict] | None = None
    functional: Callable[[str], dict] | None = None
    security: Callable[[str], dict] | None = None

    def validate(self, code: str) -> dict:
        """返回编译、功能和安全三类证据；异常转为结构化失败。

        缺失的回调记为 unmeasured（不是 pass），防止把未执行的验证
        当成通过；回调抛异常时转成 validator_exception 失败并留痕。
        """
        result: dict = {"language": self.language}
        for name, check in (
            ("syntax_or_compile", self.compile_or_syntax),
            ("functional", self.functional),
            ("security", self.security),
        ):
            if check is None:
                result[name] = {"status": "unmeasured", "details": f"{self.language} 适配器未注入 {name} 验证", "error_type": None}
                continue
            try:
                outcome = check(code)
                if isinstance(outcome, dict):
                    result[name] = outcome
                else:
                    result[name] = {"status": "pass" if bool(outcome) else "fail", "details": "", "error_type": None if outcome else f"{name}_failed"}
            except Exception as exc:
                result[name] = {"status": "fail", "error_type": "validator_exception", "details": type(exc).__name__}
        return result


def _python_compile(code: str) -> dict:
    """Python 语法检查：ast.parse，不做 Docker。"""
    import ast

    try:
        ast.parse(code)
        return {"status": "pass", "details": "ast.parse passed", "error_type": None}
    except SyntaxError as exc:
        return {"status": "fail", "details": str(exc), "error_type": "syntax_error"}


def build_python_adapter() -> LanguageAdapter:
    """构建接入本地 PLT 验证的 Python 适配器。

    功能/安全回调通过 methods.sct_agent.validation_evidence 的
    validate_generated_code 执行（本地 python -I 临时子进程）；回调缺失时
    由 LanguageAdapter.validate 记为 unmeasured。
    """
    from methods.sct_agent.validation_evidence import validate_generated_code

    def _functional(code: str) -> dict:
        result = validate_generated_code("python", code, functional=lambda c: True)
        return result.to_dict().get("functional") or {"status": "unmeasured"}

    def _security(code: str) -> dict:
        result = validate_generated_code("python", code, security=lambda c: True)
        return result.to_dict().get("security") or {"status": "unmeasured"}

    return LanguageAdapter("python", compile_or_syntax=_python_compile, functional=_functional, security=_security)


def adapter_contract(language: str) -> dict:
    """声明语言当前是否接入正式 harness；未接入项必须标记未测量。"""
    return {
        "language": language,
        "backend": "docker_harness" if language in {"python", "go", "cpp"} else "unmeasured",
        "feedback_channel": "training_only",
        "adapter_ready": language == "python",
    }
