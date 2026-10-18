"""HSK-Tree：层次化安全知识树（DOCX 第 2 章）。

所属阶段：全流程共用的记忆结构（CLE 地基）。
输入：经验节点（按 CWE 归属的安全不变量 + 语言叶）。
输出：可 JSON/JSONL 序列化的 4 层树，支持按 CWE 硬路由检索与拓扑演化。
验证证据：本模块只负责结构存储与演化，不执行任何动态验证；正确性由
   tests/test_hsk_tree.py 覆盖。
失败类型：CWE 未知时返回空分支；归并/剪枝遵循确定性阈值，不抛异常。
允许修改长期经验库：是——本树即长期记忆 M_t/M*，但写入需由门控/生命周期驱动。

4 层结构（DOCX 表 3）：
  Level 1 CWEFamilyNode（cwe 根路由，O(1) 硬过滤）
  Level 2&3 SecurityInvariantNode（高维不变量 + positive/negative 双轨 + 效用）
  Level 4 LanguageLeaf（safe_constructs / prohibited_constructs / pattern_snippet）

status 枚举（DOCX）：provisional | active | consolidated | retired
效用（DOCX 6.3）：Utility = (support_count + 1) / (regression_count + 1)
拓扑演化阈值：语义重叠 Overlap≥0.6 吸收；<0.6 新建；同 CWE 活跃节点>4 归并；效用<0.3 剪枝。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# 节点生命周期状态（DOCX 2.2 + 本次新增 unmeasured / revised）
# 说明（实测教训）：门控会产生 unmeasured 与 revised 两种终态，但早期 NODE_STATUS
#   未收录它们，导致 `cand.status = "unmeasured"` 抛 ValueError 直接中断整条运行。
#   这里补齐，并加单元测试锁住"门控所有可能的终态都在允许集合内"。
# unmeasured：门控测了但没测出差异（ΔJointPass=0）→ 不晋升、不删除，
#   保留在经验池里继续参与检索（用户拍板的"降级处理"）。不进入树的 active 集合，
#   也不会被重复审计（审计目标只筛 provisional）。
# revised：被判需要修订（如缺测 hpass_missing）→ 同样留在池里等待后续处理。
NODE_STATUS = ("provisional", "active", "consolidated", "retired",
               "unmeasured", "revised")

# 拓扑演化阈值（DOCX 6.3）
OVERLAP_ABSORB = 0.6     # TF-IDF 语义重叠 ≥ 0.6 → 就地吸收
CONSOLIDATE_MAX = 4      # 同 CWE 活跃节点 > 4 → 触发归并
UTILITY_PRUNE = 0.3      # 效用 < 0.3 → 剪枝 retired


def utility_score(support_count: int, regression_count: int) -> float:
    """DOCX 效用公式：Utility = (support+1)/(regression+1)，regression 越大效用越低。"""
    return (int(support_count) + 1) / (int(regression_count) + 1)


@dataclass
class LanguageLeaf:
    """Level 4 语言叶节点（以正文字段为准，见拍板决策 11）。

    记录某语言下该安全不变量的落地细节：
      - safe_constructs：推荐使用的安全 API / 库 / 结构（如 Python 的 hmac.compare_digest）
      - prohibited_constructs：该语言下的禁忌写法 / 易断裂反模式（如 eval、字符串拼 SQL）
      - pattern_snippet：可直接参考的最小代码片段（保持功能前提下的最小改动范式）
    消融实验（A1~A6）会分别开关这些字段的生成与注入。
    """

    language: str
    safe_constructs: list[str] = field(default_factory=list)
    prohibited_constructs: list[str] = field(default_factory=list)
    pattern_snippet: str = ""

    def has_content(self) -> bool:
        """叶节点是否有实质内容（消融实验判据：空壳叶等同没有 Level 4）。"""
        return bool(self.safe_constructs or self.prohibited_constructs
                    or (self.pattern_snippet or "").strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LanguageLeaf":
        return cls(
            language=str(value.get("language", "")),
            safe_constructs=list(value.get("safe_constructs") or []),
            prohibited_constructs=list(value.get("prohibited_constructs") or []),
            pattern_snippet=str(value.get("pattern_snippet", "")),
        )


@dataclass
class TrackRule:
    """Level 3 单条轨道规则（仅"L2/3 拆分"模式下使用）。

    DOCX 把 Level 2&3 合并为一个 SecurityInvariantNode（双轨字段内嵌）。
    拆分模式把双轨提升为独立子节点，可分别计数/检索/演化：
      - track="positive"：保持功能下的正向修复准则
      - track="negative"：破坏功能的禁忌手段（负向红线）
    拆分与否由消融实验 A2/A6 检验（用户拍板 Q1）。
    """

    rule_id: str
    track: str                      # positive | negative
    text: str                       # 规则正文
    source_kind: str = ""           # 来源跃迁类型（B_to_A / B_to_C ...）
    support_count: int = 0
    regression_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TrackRule":
        return cls(
            rule_id=str(value.get("rule_id", "")),
            track=str(value.get("track", "positive")),
            text=str(value.get("text", "")),
            source_kind=str(value.get("source_kind", "")),
            support_count=int(value.get("support_count", 0)),
            regression_count=int(value.get("regression_count", 0)),
        )


@dataclass
class SecurityInvariantNode:
    """Level 2&3 安全不变量节点（正/负双轨 + 效用统计）。"""

    invariant_id: str
    cwe: str
    high_level_invariant: str
    applicability: str = ""
    positive_principle: str = ""      # 正向修复准则（源自 B→A/D→A/C→A）
    negative_guardrail: str = ""      # 负向避坑红线（源自 B→C）
    support_count: int = 0
    regression_count: int = 0
    status: str = "provisional"
    language_leaves: dict[str, LanguageLeaf] = field(default_factory=dict)
    # 来源元数据（不区分待遇，仅用于审计追溯）：{"stage": "phase1"/"phase2"/"consolidate",
    # "kind": 跃迁类型/提取方式, "task_id": 来源任务, "state_flow": "B->C" 等}
    source: dict[str, Any] = field(default_factory=dict)
    # 【仅拆分模式使用】Level 3 轨道规则列表；合并模式下该字段为空，
    # 双轨信息内嵌在 positive_principle / negative_guardrail 两个字段里（DOCX 原设计）。
    track_rules: list[TrackRule] = field(default_factory=list)
    # 固定库Q校准独立于支持/回归计数；旧库从未学习的0/0开始。
    q_value: float = 0.0
    q_visits: int = 0

    def __post_init__(self) -> None:
        if self.status not in NODE_STATUS:
            raise ValueError(f"unknown node status: {self.status}")

    @property
    def utility(self) -> float:
        return utility_score(self.support_count, self.regression_count)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["language_leaves"] = {k: v.to_dict() for k, v in self.language_leaves.items()}
        value["track_rules"] = [r.to_dict() for r in self.track_rules]
        value["utility"] = round(self.utility, 4)
        # 消融用计数：叶节点是否真的有内容（空壳叶等同没有 Level 4）
        value["leaf_stats"] = {
            "leaves": len(self.language_leaves),
            "filled_leaves": sum(1 for lf in self.language_leaves.values() if lf.has_content()),
            "languages": sorted(self.language_leaves.keys()),
        }
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SecurityInvariantNode":
        leaves = {
            str(k): LanguageLeaf.from_dict(v) for k, v in (value.get("language_leaves") or {}).items()
        }
        return cls(
            invariant_id=str(value.get("invariant_id", "")),
            cwe=str(value.get("cwe", "")),
            high_level_invariant=str(value.get("high_level_invariant", "")),
            applicability=str(value.get("applicability", "")),
            positive_principle=str(value.get("positive_principle", "")),
            negative_guardrail=str(value.get("negative_guardrail", "")),
            support_count=int(value.get("support_count", 0)),
            regression_count=int(value.get("regression_count", 0)),
            status=str(value.get("status", "provisional")),
            language_leaves=leaves,
            source=dict(value.get("source") or {}),
            track_rules=[TrackRule.from_dict(r) for r in (value.get("track_rules") or [])],
            q_value=float(value.get("q_value", 0.0)),
            q_visits=int(value.get("q_visits", 0)),
        )


@dataclass
class CWEFamilyNode:
    """Level 1 CWE 根路由节点。"""

    cwe_id: str
    cwe_name: str = ""
    invariants: list[SecurityInvariantNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["invariants"] = [n.to_dict() for n in self.invariants]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CWEFamilyNode":
        return cls(
            cwe_id=str(value.get("cwe_id", "")),
            cwe_name=str(value.get("cwe_name", "")),
            invariants=[SecurityInvariantNode.from_dict(n) for n in (value.get("invariants") or [])],
        )


class HskTree:
    """HSK-Tree 容器：按 CWE 硬路由 + 拓扑演化。"""

    def __init__(self) -> None:
        self._families: dict[str, CWEFamilyNode] = {}

    def ensure_family(self, cwe: str, cwe_name: str = "") -> CWEFamilyNode:
        key = str(cwe)
        if key not in self._families:
            self._families[key] = CWEFamilyNode(cwe_id=key, cwe_name=cwe_name or key)
        return self._families[key]

    def family(self, cwe: str) -> CWEFamilyNode | None:
        return self._families.get(str(cwe))

    def active_invariants(self, cwe: str, language: str | None = None,
                          *, statuses: tuple[str, ...] = ("active",)) -> list[SecurityInvariantNode]:
        """返回某 CWE 下指定 status 的 Invariant 节点；language 非空时要求含对应叶。

        statuses 默认只取 active（DOCX 原设计的"active 白名单"）。
        消融实验需要放宽到 provisional：Phase1 产出的经验要等 Phase3 门控才晋升为
        active，若严格只检索 active，则 Phase1/轮1 阶段必然检索为空，
        导致 Level 3/4 的注入效果无法被测量（实测命中率仅 4/10）。
        """
        fam = self._families.get(str(cwe))
        if fam is None:
            return []
        nodes = [n for n in fam.invariants if n.status in statuses]
        if language is not None:
            nodes = [n for n in nodes if language in n.language_leaves]
        return nodes

    def insert_node(self, node: SecurityInvariantNode) -> None:
        """插入节点（根路由锁定 Level 1）。"""
        self.ensure_family(node.cwe).invariants.append(node)

    def all_families(self) -> list[CWEFamilyNode]:
        """返回全部 CWE 分支（按 cwe 排序），供调度器等遍历。"""
        return [self._families[k] for k in sorted(self._families)]

    def active_count_by_cwe(self) -> dict[str, int]:
        """各 CWE 的 active 节点数（调度器阶段一用来找薄弱 CWE）。"""
        return {
            fam.cwe_id: sum(1 for n in fam.invariants if n.status == "active")
            for fam in self.all_families()
        }

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in sorted(self._families.items())}

    def to_jsonl(self) -> list[dict]:
        """平铺成 JSONL 行（每行一个 Invariant 节点，附带 cwe 路由）。"""
        rows = []
        for cwe, fam in sorted(self._families.items()):
            for node in fam.invariants:
                d = node.to_dict()
                d["cwe"] = cwe
                rows.append(d)
        return rows


def _tokens(text: str) -> set[str]:
    """与 retriever 一致的轻量分词（英文+数字 token 与中文片段）。"""
    import re

    return set(re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", (text or "").lower()))


def tfidf_overlap(a: str, b: str) -> float:
    """两段文本的 Jaccard 词重叠度，作为 DOCX 6.3 的语义亲和度 Overlap。"""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def absorb_or_new(
    family: CWEFamilyNode,
    node: SecurityInvariantNode,
    *,
    overlap_threshold: float = OVERLAP_ABSORB,
) -> str:
    """DOCX 6.3 第 2 步：同类规则语义亲和度匹配。

    - 与现有 active 节点 TF-IDF 重叠 ≥ 阈值 → 就地吸收（合并负向红线、叶节点求并集），
      返回 "absorbed:<invariant_id>"；
    - 无匹配 → 挂载为新兄弟节点，返回 "new"。
    """
    best, best_score = None, 0.0
    for existing in family.invariants:
        if existing.status != "active":
            continue
        score = tfidf_overlap(
            existing.high_level_invariant + " " + existing.positive_principle,
            node.high_level_invariant + " " + node.positive_principle,
        )
        if score > best_score:
            best, best_score = existing, score

    if best is not None and best_score >= overlap_threshold:
        before_content = (best.negative_guardrail, {k: v.to_dict() for k, v in best.language_leaves.items()})
        # 就地吸收：负向红线合并、叶节点求并集、support 累加
        if node.negative_guardrail and node.negative_guardrail not in best.negative_guardrail:
            best.negative_guardrail = (best.negative_guardrail + "；" + node.negative_guardrail).strip("；")
        for lang, leaf in node.language_leaves.items():
            if lang in best.language_leaves:
                existing_leaf = best.language_leaves[lang]
                existing_leaf.safe_constructs = sorted(set(existing_leaf.safe_constructs) | set(leaf.safe_constructs))
                existing_leaf.prohibited_constructs = sorted(set(existing_leaf.prohibited_constructs) | set(leaf.prohibited_constructs))
            else:
                best.language_leaves[lang] = leaf
        best.support_count += node.support_count
        after_content = (best.negative_guardrail, {k: v.to_dict() for k, v in best.language_leaves.items()})
        if after_content != before_content:
            # 旧Q估计对应旧正文；单纯支持计数增加不代表新一次Q奖励。
            best.q_value, best.q_visits = 0.0, 0
        return f"absorbed:{best.invariant_id}"

    family.invariants.append(node)
    node.status = "active"
    return "new"


def prune_by_utility(family: CWEFamilyNode, *, threshold: float = UTILITY_PRUNE) -> int:
    """DOCX 6.3 第 4 步：效用 < 阈值 → retired（检索屏蔽）。返回剪枝节点数。"""
    count = 0
    for node in family.invariants:
        if node.status == "active" and node.utility < threshold:
            node.status = "retired"
            count += 1
    return count


def consolidate_family(
    family: CWEFamilyNode,
    consolidator,  # 签名 consolidator(list[SecurityInvariantNode]) -> SecurityInvariantNode（LLM 归并）
    *,
    max_active: int = CONSOLIDATE_MAX,
) -> SecurityInvariantNode | None:
    """DOCX 6.3 第 3 步：活跃节点超限 → 离线归并（LLM 提取公约数）为 1 条高阶节点。

    原分散节点归档（status 改 consolidated），新节点挂载为 active。

    注意阈值与实际规模的匹配：实测全量运行中每个 CWE 的 active 节点最多只有 3 个
    （因为门控抽样保守），而默认阈值 max_active=4 → **归并从未触发**（3 轮均为 0 次）。
    因此调用方若要真正启用归并，应把 max_active 调到与实际规模相符的值
    （见 run_closed_loop 的 --consolidate-max-active）。
    """
    actives = [n for n in family.invariants if n.status == "active"]
    if len(actives) <= max_active:
        return None
    merged = consolidator(actives)
    merged.q_value, merged.q_visits = 0.0, 0
    for n in actives:
        n.status = "consolidated"
    merged.status = "active"
    family.invariants.append(merged)
    return merged
