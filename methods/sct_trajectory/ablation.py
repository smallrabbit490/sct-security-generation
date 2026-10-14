"""消融实验配置（HSK-Tree 分层与 Level 4 的有效性检验）。

所属阶段：实验配置层，被 Phase1 seed 提取、Distillation、检索注入三处读取。
职责：用一组开关控制"生成哪些层/注入哪些层"，从而隔离各层对最终成功率的贡献。
输入：实验组名（A1~A6）。
输出：`AblationConfig` 实例，含生成开关与注入开关。
验证证据：本模块只定义开关，不产生验证结论；结论由 ablation 脚本跑真实
    生成+动态测试后汇总得到（JointPass / 功能 / 安全通过率）。
失败类型：未知组名 → 抛 ValueError（避免静默跑成基线）。
允许修改长期经验库：否——只读配置。

用户拍板（2026-09-18）的实验分组：
  A1 = L2/3 合并 + 无 L4                        （基线，等价于改造前行为）
  A2 = L2/3 拆分 + 无 L4
  A3 = L2/3 合并 + L4 仅文本原则
  A4 = L2/3 合并 + L4 safe/prohibited constructs
  A5 = L2/3 合并 + L4 再加 pattern_snippet
  A6 = L2/3 拆分 + L4 完整

回答两个问题：
  Q1（合并 vs 拆分 Level 2/3）：A1 vs A2，A5 vs A6
  Q2（Level 4 有无与多少）：A1 → A3 → A4 → A5（逐级加内容）
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# Level 4 支持的语言（用户拍板 Q3：让 LLM 凭空生成，PLT 只有 Python 也照生成）
LEVEL4_LANGUAGES = ("python", "cpp", "go", "java")

ABLATION_GROUPS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")


@dataclass
class AblationConfig:
    """一组消融开关。

    生成侧（gen_*）：prompt 是否要求 LLM 产出该层内容。
    注入侧（inject_*）：检索命中后是否把该层内容喂给生成流水线。
    两者分开，才能区分"模型没生成"与"生成了但没用上"。
    """

    group: str = "A5"
    split_level23: bool = False        # True = Level2/3 拆成 Invariant + TrackRule 两类节点
    gen_l4_text: bool = True           # L4 文本性说明（语言相关的注意事项）
    gen_l4_constructs: bool = True     # safe_constructs / prohibited_constructs
    gen_l4_snippet: bool = True        # pattern_snippet 代码片段
    inject_l4_text: bool = True
    inject_l4_constructs: bool = True
    inject_l4_snippet: bool = True
    languages: tuple[str, ...] = LEVEL4_LANGUAGES
    # 【所有组统一开启】检索时是否也纳入 provisional 经验。
    # 必须为 True，否则 Phase1/轮1 阶段检索恒为空（active 白名单），
    # Level 3/4 的注入效果无法测量，A1~A6 差异全部消失。
    retrieve_provisional: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def retrieval_statuses(self) -> tuple[str, ...]:
        """检索允许的节点状态集合。"""
        return ("active", "provisional", "consolidated") if self.retrieve_provisional else ("active",)

    @property
    def has_level4(self) -> bool:
        return bool(self.gen_l4_text or self.gen_l4_constructs or self.gen_l4_snippet)


_PRESETS: dict[str, dict] = {
    # A1 基线：完全等价于改造前（无 L4、L2/3 合并）
    "A1": dict(split_level23=False, gen_l4_text=False, gen_l4_constructs=False,
               gen_l4_snippet=False, inject_l4_text=False, inject_l4_constructs=False,
               inject_l4_snippet=False),
    # A2 只拆 L2/3，不加 L4
    "A2": dict(split_level23=True, gen_l4_text=False, gen_l4_constructs=False,
               gen_l4_snippet=False, inject_l4_text=False, inject_l4_constructs=False,
               inject_l4_snippet=False),
    # A3 只加 L4 文本
    "A3": dict(split_level23=False, gen_l4_text=True, gen_l4_constructs=False,
               gen_l4_snippet=False, inject_l4_text=True, inject_l4_constructs=False,
               inject_l4_snippet=False),
    # A4 加 safe/prohibited constructs（不加 snippet）
    "A4": dict(split_level23=False, gen_l4_text=True, gen_l4_constructs=True,
               gen_l4_snippet=False, inject_l4_text=True, inject_l4_constructs=True,
               inject_l4_snippet=False),
    # A5 完整 L4（含代码片段）——默认组
    "A5": dict(split_level23=False, gen_l4_text=True, gen_l4_constructs=True,
               gen_l4_snippet=True, inject_l4_text=True, inject_l4_constructs=True,
               inject_l4_snippet=True),
    # A6 拆分 + 完整 L4
    "A6": dict(split_level23=True, gen_l4_text=True, gen_l4_constructs=True,
               gen_l4_snippet=True, inject_l4_text=True, inject_l4_constructs=True,
               inject_l4_snippet=True),
    # A7 默认组：L2/3 合并 + **不生成 L4**（保留注入开关为 False）。
    # 用户拍板（2026-09-20）：实测四语言叶生成对本任务无可见收益，
    # 却让每个 seed 多出 4 次 LLM 调用（约占总耗时 10~15%），故默认关闭生成。
    # 注意：这与 A1「无法生成」的区别是——A7 保留代码路径与注入逻辑，
    # 需要时可用 --ablation A4/A5/A6 重新启用，便于回归对比。
    "A7": dict(split_level23=False, gen_l4_text=False, gen_l4_constructs=False,
               gen_l4_snippet=False, inject_l4_text=False, inject_l4_constructs=False,
               inject_l4_snippet=False),
}


def get_config(group: str = "A5") -> AblationConfig:
    """按组名取配置；未知组名直接报错（不静默降级成基线）。"""
    key = str(group).upper()
    if key not in _PRESETS:
        raise ValueError(f"unknown ablation group: {group}（可选 {ABLATION_GROUPS}）")
    return AblationConfig(group=key, **_PRESETS[key])


def all_configs() -> list[AblationConfig]:
    return [get_config(g) for g in ABLATION_GROUPS]


def describe() -> list[dict]:
    """给看板/报告用的实验设计说明。"""
    q1 = "Level 2/3 合并 vs 拆分"
    q2 = "Level 4 的有无与内容量"
    return [
        {"group": "A1", "split": False, "l4": "无", "answers": q2 + "（基线）", "purpose": "对照组"},
        {"group": "A2", "split": True, "l4": "无", "answers": q1, "purpose": "隔离拆分的影响"},
        {"group": "A3", "split": False, "l4": "仅文本原则", "answers": q2, "purpose": "L4 文本是否有用"},
        {"group": "A4", "split": False, "l4": "+safe/prohibited", "answers": q2,
         "purpose": "结构化构造清单是否增益"},
        {"group": "A5", "split": False, "l4": "+pattern_snippet（完整）", "answers": q2,
         "purpose": "代码片段是否增益"},
        {"group": "A6", "split": True, "l4": "完整", "answers": f"{q1} + {q2}",
         "purpose": "拆分与完整 L4 的组合"},
    ]
