"""轻量可审计 TF-IDF 检索器：不依赖外部服务，结果可复现。

所属阶段：R0/R1 训练侧经验检索与 A_audit 独立审查前的经验召回。
输入：经验卡列表（seed 或 candidate，含 cwe/principle/applicability 等字段）
     与任务查询（CWE_ID/language/description/security_policy）。
输出：按分数降序的经验卡 top-k，供代码生成 prompt 注入。
验证证据：检索本身不执行任何验证，只负责召回；候选经验是否有效由
     独立审查（A_audit）判定，检索分数不能替代有效性证据。
允许修改长期经验库：否——本模块只读取经验卡，不写回记忆。
"""

from __future__ import annotations

import math
import re
from typing import Iterable

# 分词同时覆盖英文/数字 token 与中文字符（中文经验 principle 是可检索语义）。
# 中文按连续汉字片段切分（不引入 jieba 等外部依赖，保持可复现），英文沿用
# 原有的 [a-z0-9_-]+ 规则。
_TOKEN_RE = re.compile(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", re.IGNORECASE)

# 可检索的经验字段：cwe 强匹配 + 语义文本（principle/applicability）。
_SEARCHABLE_FIELDS = ("cwe", "principle", "applicability")


def _tokens(text: str) -> set[str]:
    """把一段文本切成小写 token 集合；中英文都支持。"""
    return set(t.lower() for t in _TOKEN_RE.findall(text or ""))


class ExperienceRetriever:
    """用词频和逆文档频率计算经验相关性。

    分数由两部分组成：
    1. CWE 硬匹配加分：查询 CWE_ID 与经验 cwe **相同**时 +CWE_BONUS，
       保证同类漏洞经验优先召回（种子与候选一致对待）；不同 CWE 不加分；
    2. 语义重叠：查询 token 与经验文本（principle/applicability）的
       TF-IDF 加权重叠，中文与英文 token 均可匹配。

    无效经验召回防护（对应「检索可能召回无效经验」这一缺陷）：
    - 构造时过滤已关闭状态（demoted/retired/rejected）与无原则文本的经验，
      这些经验已被证伪或没有可检索语义，只会制造噪声；
    - search 按相关性下限截断：与查询既无 CWE 匹配也无语义重叠的经验
      （score <= min_score）不再进入 top-k，避免把无关经验塞进生成 prompt。

    候选经验（provisional）与 seed 同等参与排序；审查流程应校验
    候选是否真的进入 top-k（见 run_lifecycle_replay 的 fail-fast 断言），
    否则独立审查测不到候选经验、增量成为噪声。
    """

    CWE_BONUS = 3.0
    # 已关闭状态：被证伪/退役/拒绝的经验不应再参与检索召回。
    _CLOSED_STATUS = frozenset({"demoted", "retired", "rejected"})

    def __init__(self, cards: Iterable[dict] = ()) -> None:
        self.cards = [card for card in cards if self._usable(card)]
        # 预计算每张卡片的 token 集合与全库词频，避免 search 反复扫描。
        self._card_tokens: list[set[str]] = []
        self._corpus_freq: dict[str, int] = {}
        for card in self.cards:
            tokens = _tokens(" ".join(str(card.get(k, "")) for k in _SEARCHABLE_FIELDS))
            self._card_tokens.append(tokens)
            for token in tokens:
                self._corpus_freq[token] = self._corpus_freq.get(token, 0) + 1

    @staticmethod
    def _usable(card: dict) -> bool:
        """判定经验是否可参与检索：原则非空且状态未关闭。

        status 缺省视为 seed（来源池经验）；demoted/retired/rejected 是
        被证伪或退役的状态，必须从召回池剔除；无原则文本的经验没有
        可检索语义，直接过滤，避免占位噪声。
        """
        status = str(card.get("status") or "seed")
        if status in ExperienceRetriever._CLOSED_STATUS:
            return False
        return bool(str(card.get("principle") or "").strip())

    def score(self, query_tokens: set[str], card_index: int, *, query_cwe: str = "") -> float:
        """返回单张经验卡对查询的相关性分数；只用于排序，不判定有效性。

        CWE 加分只在「查询 CWE 与经验 cwe 完全一致」时生效；此前实现只要
        经验卡有任意非空 cwe 字段就加满 CWE_BONUS，导致不同 CWE 的经验
        被错误召回（检索到无效经验）。修复后不同 CWE 的经验只能靠语义重叠
        得分，不再与同 CWE 经验同权竞争 top-k。
        """
        card = self.cards[card_index]
        card_cwe = str(card.get("cwe") or "").strip()
        cwe_hit = self.CWE_BONUS if (query_cwe and card_cwe and card_cwe == query_cwe) else 0.0
        overlap = 0.0
        card_tokens = self._card_tokens[card_index]
        for token in query_tokens & card_tokens:
            freq = self._corpus_freq.get(token, 0)
            # IDF 权重：词在库中越罕见，命中越有价值；+2 平滑避免除零。
            overlap += 1.0 / math.log(2 + freq)
        return cwe_hit + overlap

    def search(self, task: dict, limit: int = 3, *, min_score: float = 0.0) -> list[dict]:
        """按相关性返回 top-k 经验卡；空库返回空列表。

        查询字段与训练 prompt 使用同一来源（CWE_ID、language、description、
        security_policy），保证检索与生成输入一致。相关性下限 min_score
        用于截断「与任务无任何匹配」的经验：score <= min_score 的经验与
        查询既不同 CWE 也无 token 重叠，属无效召回，直接停在此处（已按
        分数降序排列，后续只会更低）。
        """
        if not self.cards:
            return []
        query = " ".join(
            str(task.get(k, "")) for k in ("CWE_ID", "language", "description", "security_policy")
        )
        query_tokens = _tokens(query)
        query_cwe = str(task.get("CWE_ID") or "").strip()
        scored = sorted(
            range(len(self.cards)),
            key=lambda i: (
                -self.score(query_tokens, i, query_cwe=query_cwe),
                str(self.cards[i].get("id", "")),
            ),
        )
        results: list[dict] = []
        for i in scored:
            if self.score(query_tokens, i, query_cwe=query_cwe) <= min_score:
                break
            results.append(self.cards[i])
            if len(results) >= max(0, limit):
                break
        return results
