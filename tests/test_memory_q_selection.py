"""共同召回与Q选择的契约；确定性余弦替身，不请求embedding或LLM。"""
import json

import pytest

from methods.sct_trajectory.context_pipeline import experience_text
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever
from methods.sct_trajectory.semantic_retrieval import card_embedding_text, semantic_select, semantic_value_select


class Scores:
    model = "offline-test-scores"

    def cosine_scores(self, query, texts):
        return [float(json.loads(t)["high_level_invariant"].split()[-1]) for t in texts]


def memories():
    return [SecurityInvariantNode(str(i), "22", f"rule {s}",
                q_value=-1 if i < 3 else 1,
                language_leaves={"python": LanguageLeaf("python")})
            for i, s in enumerate([0.9, 0.8, 0.7, 0.6, 0.1])]


def test_legacy_and_value_modes_share_recall_but_not_selector():
    nodes = memories()
    task = {"description": "rule", "language": "python"}
    _, legacy = semantic_select(task, nodes, lambda p: {"selected": [1, 2, 3]}, Scores())
    sim, baseline = semantic_value_select(task, nodes, Scores(), delta=0.5, lambda_q=0)
    learned, q_trace = semantic_value_select(task, nodes, Scores(), delta=0.5, lambda_q=0.5)
    assert legacy["candidate_ids"] == baseline["candidate_ids"] == q_trace["candidate_ids"]
    assert [n.invariant_id for n in sim] == ["0", "1", "2"]
    assert [n.invariant_id for n in learned] == ["0", "3", "1"]


def test_retriever_new_modes_require_threshold_and_preserve_adoption_projection():
    nodes = memories()
    retired = SecurityInvariantNode("retired", "22", "rule 0.99", q_value=99, status="retired",
                                    language_leaves={"python": LanguageLeaf("python")})
    def no_selector(prompt):
        raise AssertionError("value selector must not call an LLM")
    with pytest.raises(ValueError, match="semantic_delta"):
        HskTreeRetriever(HskTree(), retrieval_mode="semantic_q", embedding_client=Scores())
    retriever = HskTreeRetriever(HskTree(), requester=no_selector, retrieval_mode="semantic_q",
        embedding_client=Scores(), semantic_delta=0.5, lambda_q=0.5)
    cards = retriever.search({"description": "rule", "language": "python"}, pool_nodes=nodes+[retired])
    assert [c["invariant_id"] for c in cards] == ["0", "3", "1"]
    assert "retired" not in retriever.last_hier_trace["candidate_ids"]
    assert "q_value" not in experience_text(cards)
    assert "q_z" not in experience_text(cards)
    before = card_embedding_text(nodes[0])
    nodes[0].q_value = 0.99
    assert card_embedding_text(nodes[0]) == before
