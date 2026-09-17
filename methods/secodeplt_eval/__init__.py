"""SeCodePLT 官方评测方式的本地移植（评测工具，不参与经验库更新）。

所属阶段：训练侧/评测侧的代码动态验证（与 `methods/sct_agent/validation_evidence`
的本地验证器互补）。本模块把官方仓库 `ucsb-mlsec/SeCodePLT`（论文 arXiv
2410.11096）的 Python 评测方式移植到本仓库：
- 模板注入：把 setup / 生成代码 / testcases 源码注入官方 `unittest_template`，
  与被测函数重命名后整体作为一个脚本执行；
- 执行：默认用本地 `python -I` 子进程（等价于官方 Docker 容器内执行，但零
  Docker 开销、不产生 VHDX 虚拟盘增长）；可选 Docker 常驻容器后端（官方原样）；
- 打分：capability（功能）/ safety（安全）两组逐用例 1/-1/-2 结果 → 平均分，
  联合通过 = 功能与安全都全过（与官方「capability 不过安全即 0」口径一致）。

验证证据：分数完全来自测试用例的真实执行结果（编译/功能/安全/超时），不包含
模型自评；未执行的分组保持 unmeasured。
允许修改长期经验库：否——本模块只评测代码，不写回记忆。
"""

from .executor import run_testcases_local
from .scoring import joint_pass, testcase_evaluation

__all__ = [
    "run_testcases_local",
    "testcase_evaluation",
    "joint_pass",
]
