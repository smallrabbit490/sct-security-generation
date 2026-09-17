"""SCT 轨迹对比式自进化（新方案）实现包。

对外暴露四态判定、轨迹转移对比、四步子 Agent 流水线、检索对齐与闭环编排。

信号边界（硬性红线）：本包所有在线进化信号只能来自训练侧 PLT
（D_init / D_grow / D_gate）；Base/Plus 是冻结后的最终离线评测，其测试结果
永不回流到经验生成、门控、检索对齐或模型更新。
"""

from .four_state import FourState, state_from_evidence, transition_kind

__all__ = ["FourState", "state_from_evidence", "transition_kind"]