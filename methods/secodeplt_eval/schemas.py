"""与官方 SeCodePLT 数据结构对齐的最小审计记录结构（零外部依赖）。

所属阶段：SeCodePLT 评测的输入/输出数据定义（对应官方
`virtue_code_eval/code_tasks/safety/generation/secodeplt/utils.py` 与
`executor_docker/docker/python-env/run_test.py`）。
字段含义与官方一致；官方用 pydantic，这里用 dataclass 保持零新增依赖。
本模块不包含 API key、未脱敏 prompt、隐藏测试输入或答案常量。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TaskDescription:
    """任务契约描述：函数名、功能描述、安全策略、上下文、参数/返回/异常约定。"""

    function_name: str
    description: str
    security_policy: str
    context: str
    arguments: str
    return_: str  # 官方字段名为 return，asdict 时由 to_dict 重命名
    raise_: str


@dataclass
class GroundTruth:
    """漏洞/补丁三段代码：code_before + vulnerable_code + patched_code + code_after。"""

    code_before: str
    vulnerable_code: str
    patched_code: str
    code_after: str


@dataclass
class Unittest:
    """测试夹具：setup 是导入与全局变量源码，testcases 是定义
    ``testcases = {"capability": [...], "safety": [...]}`` 的源码字符串。"""

    setup: str
    testcases: str


@dataclass
class CWEData:
    """一条 SeCodePLT 任务记录（对应官方 data.json 的一行）。"""

    CWE_ID: str
    CVE_ID: str = ""
    task_description: dict | None = None
    ground_truth: dict | None = None
    unittest: dict | None = None
    install_requires: list[str] = field(default_factory=list)
    rule: str = ""
    index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestCodeParams:
    """执行器入参：把 setup / 生成代码 / testcases 源码注入官方模板所需的一切。"""

    setup: str
    code: str
    testcases: str
    func_name: str
    install_requires: list[str] = field(default_factory=list)


@dataclass
class TestCodeOutput:
    """执行器输出：capability/safety 两组逐用例结果（1=通过，-1=运行错误，
    -2=超时），以及整段测试脚本的总运行秒数。"""

    capability: list[int]
    safety: list[int]
    runtime: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
