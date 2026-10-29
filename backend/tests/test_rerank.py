"""Reranking: provider fallback, retrieval wiring, abstain threshold and audit logging.

No model is downloaded: the cross-encoder and NVIDIA calls are replaced by small fakes.
"""

import io
import json

import pytest

from database.connection import audit_log_collection, documents_chunk_collection
from services import rerank_service, retrieval_service
from services.access.policy import UserContext

DEV = UserContext("u-dev", "Dev", "dev@x", "IT", "DEVELOPER", "Developer", "internal", frozenset())

FAKE_EMBEDDING = lambda: type("E", (), {"embed_query": lambda self, q: [1.0, 0.0]})()


def keyword_scorer(scores_by_text):
    """Fake cross-encoder: score is looked up by chunk text; records what it was shown."""
    seen = []

    def score(question, texts):
        seen.extend(texts)
        return [scores_by_text.get(text, 0.0) for text in texts]

    score.seen = seen
    return score


@pytest.fixture()
def local_reranker(monkeypatch):
    monkeypatch.setattr(rerank_service, "RERANK_PROVIDER", "local")
    return monkeypatch


# ---- 1. rerank_service ----------------------------------------------------------

def test_rerank_sorts_by_cross_encoder_score_and_tags_chunks(local_reranker):
    local_reranker.setattr(rerank_service, "_score_local", keyword_scorer({"a": 0.1, "b": 0.9, "c": 0.5}))
    chunks = [{"chunk_uuid": x, "text": x, "score": 0.99} for x in "abc"]

    result = rerank_service.rerank("q", chunks)

    assert [c["chunk_uuid"] for c in result] == ["b", "c", "a"]
    assert result[0]["rerank_score"] == 0.9 and result[0]["rerank_provider"] == "local"
    assert "rerank_score" not in chunks[0]  # input left untouched


def test_nvidia_failure_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(rerank_service, "RERANK_PROVIDER", "nvidia")

    def nvidia_down(question, texts):
        raise TimeoutError("no answer")

    monkeypatch.setattr(rerank_service, "_score_nvidia", nvidia_down)
    monkeypatch.setattr(rerank_service, "_score_local", keyword_scorer({"a": 0.7}))

    result = rerank_service.rerank("q", [{"text": "a"}])

    assert result[0]["rerank_provider"] == "local" and result[0]["rerank_score"] == 0.7


def test_every_provider_failing_returns_none(local_reranker):
    def broken(question, texts):
        raise ImportError("sentence_transformers missing")

    local_reranker.setattr(rerank_service, "_score_local", broken)
    assert rerank_service.rerank("q", [{"text": "a"}]) is None


def test_provider_none_disables_reranking(monkeypatch):
    monkeypatch.setattr(rerank_service, "RERANK_PROVIDER", "none")
    assert rerank_service.rerank("q", [{"text": "a"}]) is None


def test_nvidia_logits_are_mapped_back_by_index_and_squashed(monkeypatch):
    monkeypatch.setattr(rerank_service, "NVIDIA_API_KEY", "test-key")
    sent = {}

    def fake_urlopen(request, timeout):
        sent["body"] = json.loads(request.data)
        sent["auth"] = request.headers["Authorization"]
        payload = {"rankings": [{"index": 1, "logit": 4.0}, {"index": 0, "logit": -4.0}]}
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(rerank_service.urllib.request, "urlopen", fake_urlopen)

    scores = rerank_service._score_nvidia("q", ["first", "second"])

    assert sent["body"]["query"] == {"text": "q"}
    assert [p["text"] for p in sent["body"]["passages"]] == ["first", "second"]
    assert sent["auth"] == "Bearer test-key"
    assert scores[0] < 0.05 and scores[1] > 0.95


def test_low_confidence_only_when_reranked_and_below_threshold(monkeypatch):
    monkeypatch.setattr(rerank_service, "RERANK_MIN_SCORE", 0.3)

    assert rerank_service.is_low_confidence([{"rerank_score": 0.1}, {"rerank_score": 0.2}])
    assert not rerank_service.is_low_confidence([{"rerank_score": 0.1}, {"rerank_score": 0.5}])
    assert not rerank_service.is_low_confidence([{"score": 0.01}])  # not reranked: never abstain


# ---- 2. retrieval wiring --------------------------------------------------------

def vector_hits(n, document_uuid=lambda i: f"d{i}"):
    return [{"chunk_uuid": f"c{i}", "document_uuid": document_uuid(i), "text": f"t{i}", "score": 1 - i / 100}
            for i in range(n)]


def test_retrieval_reranks_a_wide_pool_and_returns_top_n(client, local_reranker):
    calls = []

    def fake_vector_search(**kw):
        calls.append(kw)
        return vector_hits(50) if not kw.get("document_uuids") else []

    local_reranker.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    local_reranker.setattr(retrieval_service, "_vector_search", fake_vector_search)
    local_reranker.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    local_reranker.setattr(retrieval_service, "_find_entity_chunk_uuids", lambda q: [])
    # The reranker prefers the chunks the vector search ranked LAST.
    scorer = keyword_scorer({f"t{i}": i / 100 for i in range(50)})
    local_reranker.setattr(rerank_service, "_score_local", scorer)

    result = retrieval_service.retrieve_relevant_chunks("q", DEV, limit=10)

    assert calls[0]["candidate_limit"] == rerank_service.RERANK_CANDIDATES
    assert len(scorer.seen) == 50
    top_n = rerank_service.RERANK_TOP_N
    assert [c["chunk_uuid"] for c in result] == [f"c{i}" for i in range(49, 49 - top_n, -1)]  # top N by rerank
    assert all("rerank_score" in c for c in result)


def test_retrieval_still_caps_chunks_per_document_after_rerank(client, local_reranker):
    local_reranker.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    local_reranker.setattr(retrieval_service, "_vector_search",
                           lambda **kw: vector_hits(10, document_uuid=lambda i: "same-doc" if i < 8 else f"d{i}"))
    local_reranker.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    local_reranker.setattr(retrieval_service, "_find_entity_chunk_uuids", lambda q: [])
    local_reranker.setattr(rerank_service, "_score_local", keyword_scorer({f"t{i}": 1 - i / 10 for i in range(10)}))

    result = retrieval_service.retrieve_relevant_chunks("q", DEV, limit=10)

    assert sum(c["document_uuid"] == "same-doc" for c in result) == 3


def test_reranker_failure_keeps_the_original_selection(client, local_reranker):
    def broken(question, texts):
        raise RuntimeError("model failed to load")

    local_reranker.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    local_reranker.setattr(retrieval_service, "_vector_search", lambda **kw: vector_hits(20))
    local_reranker.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    local_reranker.setattr(retrieval_service, "_find_entity_chunk_uuids", lambda q: [])
    local_reranker.setattr(rerank_service, "_score_local", broken)

    result = retrieval_service.retrieve_relevant_chunks("q", DEV, limit=10)

    assert [c["chunk_uuid"] for c in result] == [f"c{i}" for i in range(10)]
    assert not any("rerank_score" in c for c in result)


def test_reranker_never_sees_a_chunk_the_user_cannot_read(client, local_reranker):
    """Red-team: entity graph points at a restricted chunk; only permitted text reaches the scorer."""
    for chunk_uuid, classification, access in [
        ("open", "internal", {"departments": [], "roles": [], "users": []}),
        ("ceo-only", "restricted", {"departments": [], "roles": ["CEO"], "users": []}),
    ]:
        documents_chunk_collection.insert_one({
            "chunk_uuid": chunk_uuid, "document_uuid": f"d-{chunk_uuid}", "text": f"text of {chunk_uuid}",
            "source": "x.pdf", "page": 1, "embedding": [1.0, 0.0],
            "classification": classification, "department_code": None, "access": access,
        })

    local_reranker.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    local_reranker.setattr(retrieval_service, "_vector_search",
                           lambda **kw: [{"chunk_uuid": "v1", "document_uuid": "d1", "text": "vector text", "score": 0.5}])
    local_reranker.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    local_reranker.setattr(retrieval_service, "_find_entity_chunk_uuids", lambda q: ["ceo-only", "open"])
    scorer = keyword_scorer({"text of ceo-only": 1.0, "text of open": 0.6, "vector text": 0.4})
    local_reranker.setattr(rerank_service, "_score_local", scorer)

    result = retrieval_service.retrieve_relevant_chunks("Who manages Project Atlas?", DEV)

    assert "text of ceo-only" not in scorer.seen
    assert [c["chunk_uuid"] for c in result] == ["open", "v1"]


# ---- 3. /api/rag/ask: abstain + audit --------------------------------------------

def reranked_chunk(score):
    return {"chunk_uuid": "c1", "text": "Notice period is 30 days.", "source": "Policy.pdf", "page": 3,
            "document_uuid": "d1", "rerank_score": score, "rerank_provider": "local"}


def test_low_rerank_score_abstains_without_calling_the_llm(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    monkeypatch.setattr(rerank_service, "RERANK_MIN_SCORE", 0.3)
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: [reranked_chunk(0.05)])

    def boom(*a, **k):
        raise AssertionError("LLM must not run on low-confidence evidence")

    monkeypatch.setattr("routes.rag_routes.generate_answer", boom)

    r = client.post("/api/rag/ask", headers=dev, json={"question": "who won the world cup?"})

    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "I could not find this information in the accessible documents."
    assert body["sources"] == [] and body["conversation_id"]

    entry = audit_log_collection.find_one({"action": "rag.ask"})
    assert entry["after"]["abstained"] == "low_rerank_score"
    assert entry["after"]["rerank"]["top_score"] == 0.05


def test_confident_answer_logs_rerank_scores_and_keeps_source_shape(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    monkeypatch.setattr(rerank_service, "RERANK_MIN_SCORE", 0.3)
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: [reranked_chunk(0.92)])
    monkeypatch.setattr("routes.rag_routes.generate_answer", lambda question, context: "30 days.")

    r = client.post("/api/rag/ask", headers=dev, json={"question": "notice period?"})

    assert r.status_code == 200 and r.json()["answer"] == "30 days."
    assert r.json()["sources"] == [{"source": "Policy.pdf", "page": 3, "document_uuid": "d1"}]  # no score leaks to UI

    rerank = audit_log_collection.find_one({"action": "rag.ask"})["after"]["rerank"]
    assert rerank["provider"] == "local" and rerank["top_score"] == 0.92
    assert rerank["chunks"] == [{"chunk_uuid": "c1", "document_uuid": "d1", "page": 3, "score": 0.92}]


def test_a_refused_first_question_still_starts_a_real_conversation(client, make_user, monkeypatch):
    """Regression: a no-answer reply used to return no conversation_id, so the follow-up failed."""
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    answers = iter([[], [reranked_chunk(0.9)]])
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: next(answers))
    monkeypatch.setattr("routes.rag_routes.generate_answer", lambda question, context: "30 days.")

    first = client.post("/api/rag/ask", headers=dev, json={"question": "unknown thing?"}).json()
    second = client.post("/api/rag/ask", headers=dev,
                         json={"question": "notice period?", "conversation_id": first["conversation_id"]})

    assert second.status_code == 200 and second.json()["conversation_id"] == first["conversation_id"]
    history = client.get(f"/api/chat/conversations/{first['conversation_id']}", headers=dev).json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant", "user", "assistant"]
