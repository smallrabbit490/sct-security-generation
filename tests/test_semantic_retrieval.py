"""真实向量检索的离线契约测试；不调用模型、不写长期经验。"""
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.semantic_retrieval import (
    EmbeddingClient, EmbeddingError, card_embedding_text, query_embedding_text,
    semantic_select,
)


def node(identifier, **kw):
    return SecurityInvariantNode(identifier, "89", "Use parameterized SQL", applicability="SQL values",
        language_leaves={"python": LanguageLeaf("python")}, **kw)


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()


def endpoint(monkeypatch, vectors=None):
    calls = []
    def open_request(request, timeout):
        data = json.loads(request.data)
        calls.append(data)
        embeddings = vectors or [[1.0, 0.0] for _ in data["input"]]
        return Response({"data": [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(embeddings)))],
                         "usage": {"prompt_tokens": len(data["input"]), "total_tokens": len(data["input"])}})
    monkeypatch.setattr("urllib.request.urlopen", open_request)
    return calls


def client(tmp_path, **kw):
    return EmbeddingClient(cache_path=tmp_path / "vectors.sqlite", key_loader=lambda: "not-a-real-key", **kw)


def test_cache_content_address_and_order(tmp_path, monkeypatch):
    calls = endpoint(monkeypatch)
    c = client(tmp_path)
    assert c.embed(["a", "b", "a"]) == [[1., 0.]] * 3
    assert len(calls) == 1 and calls[0]["input"] == ["a", "b"]
    assert client(tmp_path).embed(["b"]) == [[1., 0.]]
    assert len(calls) == 1
    c.embed(["changed"])
    client(tmp_path, model="text-embedding-3-small").embed(["a"])
    assert len(calls) == 3
    assert c.usage["calls"] == 2 and c.usage["total_tokens"] == 3


@pytest.mark.parametrize("vectors", [[[math.nan, 1]], [[0, 0]], [[1, 0], [1, 0, 0]]])
def test_invalid_vectors_fail_closed(tmp_path, monkeypatch, vectors):
    endpoint(monkeypatch, vectors)
    with pytest.raises(EmbeddingError): client(tmp_path).embed([str(i) for i in range(len(vectors))])


def test_dimension_consistency_across_batches(tmp_path, monkeypatch):
    endpoint(monkeypatch, [[1, 0]])
    c = client(tmp_path)
    c.embed(["a"])
    endpoint(monkeypatch, [[1, 0, 0]])
    with pytest.raises(EmbeddingError): c.embed(["b"])


def test_threads_share_cached_requests(tmp_path, monkeypatch):
    calls = endpoint(monkeypatch)
    c = client(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(lambda _: c.embed(["same"]), range(20)))
    assert len(calls) == 1 and len(result) == 20


def test_query_excludes_private_fields():
    query = query_embedding_text({"description": "Public contract", "unit_test": "SECRET",
                                  "hidden_tests": "SECRET", "threat_analysis": {"sources": ["request"]}})
    assert "SECRET" not in query and "request" in query


def test_query_preserves_entry_point_and_full_parameter_contract():
    public = {"function_name": "lookup", "signature": "lookup(user_id: str) -> dict",
              "arguments": [{"name": "user_id", "type": "str", "description": "Untrusted value"}],
              "return_type": "dict", "return_description": "Matched row or empty dict",
              "parameters": {"user_id": "str"}, "entry_point": "lookup", "exceptions": ["ValueError"]}
    assert json.loads(query_embedding_text(public)) == public


class FakeEmbeddings:
    model = "fake"
    def embed(self, texts): return [[1., 0.] if "SQL" in text else [0., 1.] for text in texts]


def select_payload(ids):
    return {"choices": [{"message": {"content": json.dumps({"selected": ids})}}]}


def test_selection_status_language_no_pinning_and_english():
    cards = [node("same", source={"task_id": "q"}), node("other"), node("retired", status="retired")]
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        return select_payload([1])
    chosen, trace = semantic_select({"task_id": "q", "language": "python", "description": "SQL query"}, cards, request, FakeEmbeddings())
    assert [n.invariant_id for n in chosen] == ["other"]
    assert trace["status"] == "completed" and "retired" not in trace["candidate_ids"]
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in prompts[0])
    assert len(trace["query_hash"]) == 64


@pytest.mark.parametrize("response", [select_payload([2]), select_payload([1, 1]), {"choices": []}])
def test_selection_invalid_output_no_fallback(response):
    chosen, trace = semantic_select({"language": "python", "description": "SQL"}, [node("x")], lambda _: response, FakeEmbeddings())
    assert chosen == [] and trace["status"] == "error"


def test_zero_selection_valid():
    chosen, trace = semantic_select({"language": "python", "description": "SQL"}, [node("x")], lambda _: select_payload([]), FakeEmbeddings())
    assert chosen == [] and trace["status"] == "completed"


def test_changed_applicability_changes_embedding_text():
    item = node("x")
    first = card_embedding_text(item)
    item.applicability = "Only database values, never identifiers"
    assert first != card_embedding_text(item)


def test_bounded_batches_and_prewarm(tmp_path, monkeypatch):
    calls = endpoint(monkeypatch)
    c = client(tmp_path)
    c.embed([f"text {i}" for i in range(70)])
    assert [len(call["input"]) for call in calls] == [32, 32, 6]
    c.prewarm([node("x")])
    before = len(calls)
    c.prewarm([node("x")])
    assert len(calls) == before


def test_matrix_reused_and_invalidated(tmp_path, monkeypatch):
    calls = endpoint(monkeypatch)
    c = client(tmp_path)
    assert c.cosine_scores("query", ["a", "b"]) == [1., 1.]
    matrix = c._matrix
    c.cosine_scores("other query", ["a", "b"])
    assert c._matrix is matrix
    assert len(calls) == 3
    c.cosine_scores("query", ["a", "b", "c"])
    assert c._matrix is not matrix and calls[-1]["input"] == ["c"]


def test_invalid_response_indexes(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response({"data": [
        {"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [1, 0]}]}))
    with pytest.raises(EmbeddingError, match="indexes"):
        client(tmp_path).embed(["a", "b"])


def test_secret_not_in_http_error(tmp_path, monkeypatch):
    def error(*_a, **_k): raise RuntimeError("not-a-real-key secret response")
    monkeypatch.setattr("urllib.request.urlopen", error)
    with pytest.raises(EmbeddingError) as exc:
        client(tmp_path).embed(["a"])
    assert "secret" not in str(exc.value) and "not-a-real-key" not in str(exc.value)


def test_extra_selector_explanation_rejected():
    response = select_payload([1])
    value = json.loads(response["choices"][0]["message"]["content"])
    value["reason"] = "适用于此题"
    response["choices"][0]["message"]["content"] = json.dumps(value)
    chosen, trace = semantic_select({"language": "python", "description": "SQL"}, [node("x")], lambda _: response, FakeEmbeddings())
    assert chosen == [] and trace["errors"] == ["selector_invalid_schema"]


def test_oversized_card_is_explicit_not_truncated():
    card = node("x")
    card.applicability = "X" * 13000
    chosen, trace = semantic_select({"language": "python", "description": "SQL"}, [card], lambda _: pytest.fail("no candidates"), FakeEmbeddings())
    assert not chosen and trace["excluded"][0]["reason"] == "card_budget_exceeded"


def test_semaphore_queue_wait_is_bounded(tmp_path, monkeypatch):
    calls = endpoint(monkeypatch)
    c = client(tmp_path, semaphore=threading.Semaphore(0), gate_wait_timeout=.03)
    started = time.monotonic()
    with pytest.raises(EmbeddingError, match="gate_wait_timeout"):
        c.embed(["a"])
    assert time.monotonic() - started < 1 and not calls


def test_hard_timeout_retains_slot_until_http_returns(tmp_path, monkeypatch):
    release = threading.Event()
    gate = threading.Semaphore(1)
    def slow(*args, **kwargs):
        release.wait(3)
        return Response({"data": [{"index": 0, "embedding": [1, 0]}], "usage": {"total_tokens": 7}})
    monkeypatch.setattr("urllib.request.urlopen", slow)
    c = client(tmp_path, semaphore=gate, hard_timeout=.03, gate_wait_timeout=.03)
    try:
        with pytest.raises(EmbeddingError, match="hard_timeout"):
            c.embed(["a"])
        assert not gate.acquire(blocking=False)
        with pytest.raises(EmbeddingError, match="gate_wait_timeout"):
            c.embed(["b"])
    finally:
        release.set()
    assert gate.acquire(timeout=1)
    gate.release()
    assert c.usage["calls"] == 1 and c.usage["total_tokens"] == 7


def test_duplicate_flight_wait_deadline(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()
    c = client(tmp_path, flight_wait_timeout=.03)
    def slow(_texts):
        started.set()
        release.wait(3)
        return [[1., 0.]]
    monkeypatch.setattr(c, "_request", slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(c.embed, ["a"])
        assert started.wait(1)
        try:
            with pytest.raises(EmbeddingError, match="flight_wait_timeout"):
                c.embed(["a"])
        finally:
            release.set()
        assert future.result(timeout=1) == [[1., 0.]]


def test_missing_vector_explicit_error(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response({"data": [{"index": 0}]}))
    with pytest.raises(EmbeddingError, match="missing_embedding_vector"):
        client(tmp_path).embed(["a"])


def test_matrix_lock_wait_is_bounded(tmp_path):
    c = client(tmp_path, flight_wait_timeout=.03)
    c._index_lock.acquire()
    try:
        with pytest.raises(EmbeddingError, match="index_wait_timeout"):
            c.cosine_scores("query", ["card"])
    finally:
        c._index_lock.release()


def test_missing_vectors_trace_classified():
    embeddings = FakeEmbeddings()
    embeddings.embed = lambda _: []
    cards, trace = semantic_select({"language": "python", "description": "SQL"}, [node("x")], lambda _: select_payload([]), embeddings)
    assert not cards and trace["errors"] == ["embedding_vector_count"]
