from datetime import datetime, timezone

from conftest import login
from database.connection import documents_chunk_collection, documents_collection
from services.access.policy import build_document_filter
from services import retrieval_service
from services.access.policy import UserContext
from test_api import add_doc  # noqa: E402


def add_chunk(document_uuid, **fields):
    documents_chunk_collection.insert_one({
        "chunk_uuid": f"c-{document_uuid}", "document_uuid": document_uuid, "text": "secret text",
        "source": document_uuid, "page": 1, "embedding": [0.1], **fields,
    })


def test_vector_query_carries_the_permission_filter(monkeypatch):
    captured = {}

    class FakeCollection:
        def aggregate(self, pipeline):
            captured["pipeline"] = pipeline
            return []

    monkeypatch.setattr(retrieval_service, "documents_chunk_collection", FakeCollection())
    monkeypatch.setattr(retrieval_service, "get_embedding", lambda: type("E", (), {"embed_query": lambda self, q: [0.0]})())

    ctx = UserContext("u1", "n", "e@x", "IT", "DEVELOPER", "Developer", "internal", frozenset())
    retrieval_service.retrieve_relevant_chunks("q", ctx)

    stage = captured["pipeline"][0]["$vectorSearch"]
    assert stage["filter"] == build_document_filter(ctx)  # applied inside the query, not after top-k


def test_ask_uses_only_permitted_chunks_and_cites_them(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    seen = {}

    def fake_retrieve(question, ctx, limit=5):
        seen["ctx"] = ctx
        return [{"text": "Notice period is 30 days.", "source": "Policy.pdf", "page": 3, "document_uuid": "d1"}]

    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr("routes.rag_routes.generate_answer", lambda question, context: f"Answer based on: {context[:20]}")

    r = client.post("/api/rag/ask", headers=dev, json={"question": "notice period?"})
    assert r.status_code == 200
    assert r.json()["sources"] == [{"source": "Policy.pdf", "page": 3, "document_uuid": "d1"}]
    assert seen["ctx"].role_code == "DEVELOPER"  # retrieval ran as the caller, not as an admin


def test_ask_with_nothing_permitted_does_not_call_the_llm(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: [])

    def boom(*a, **k):
        raise AssertionError("LLM must not run without permitted evidence")

    monkeypatch.setattr("routes.rag_routes.generate_answer", boom)
    r = client.post("/api/rag/ask", headers=dev, json={"question": "profit on project x?"})
    assert r.status_code == 200 and r.json()["sources"] == []


def test_ask_requires_login_and_valid_question(client, make_user):
    assert client.post("/api/rag/ask", json={"question": "hi"}).status_code == 401
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.post("/api/rag/ask", headers=dev, json={"question": ""}).status_code == 422


def test_changing_document_access_updates_its_chunks_and_delete_removes_them(client, admin):
    add_doc("d1", "internal")
    add_chunk("d1", classification="internal", department_code=None, access={"departments": [], "roles": [], "users": []})

    r = client.patch("/api/documents/d1/access", headers=admin,
                     json={"department_code": "FIN", "classification": "restricted", "access": {"roles": ["CEO"]}})
    assert r.status_code == 200

    chunk = documents_chunk_collection.find_one({"document_uuid": "d1"})
    assert chunk["classification"] == "restricted" and chunk["department_code"] == "FIN"
    assert chunk["access"]["roles"] == ["CEO"]

    assert client.delete("/api/documents/d1", headers=admin).status_code == 200
    assert documents_chunk_collection.count_documents({"document_uuid": "d1"}) == 0


def test_scan_and_ingest_requires_documents_manage(client, make_user):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.post("/api/documents/scan-and-ingest", headers=dev, json={"folder_path": "."}).status_code == 403
    assert client.post("/api/documents/d1/ingest", headers=dev).status_code == 403
