"""Regression + red-team tests from the full code review (each one pins a bug that was found and fixed)."""

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from conftest import PASSWORD
from database.connection import audit_log_collection, chat_conversations_collection, users_collection
from main import app
from services import llm_service
from test_api import add_doc
from utils.security import ALGORITHM, SECRET_KEY

PUBLIC_ROUTES = {("POST", "/auth/login"), ("GET", "/")}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def forge(payload, key=SECRET_KEY, algorithm=ALGORITHM):
    return jwt.encode(payload, key, algorithm=algorithm)


def stub_answering(monkeypatch):
    chunk = {"text": "Notice period is 30 days.", "source": "Policy.pdf", "page": 1, "document_uuid": "d1"}
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: [chunk])
    monkeypatch.setattr("routes.rag_routes.generate_answer", lambda question, context: "30 days.")


def ask(client, headers, question="notice period?", conversation_id=None):
    return client.post("/api/rag/ask", headers=headers, json={"question": question, "conversation_id": conversation_id})


# ---- authentication: forged / stale tokens --------------------------------------------------

def test_expired_token_is_rejected(client, admin):
    uuid = users_collection.find_one({"email": "root@nexora.com"})["user_uuid"]
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = forge({"sub": uuid, "iat": past - timedelta(hours=1), "exp": past})
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, admin):
    uuid = users_collection.find_one({"email": "root@nexora.com"})["user_uuid"]
    token = forge({"sub": uuid, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, key="y" * 48)
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_unsigned_alg_none_token_is_rejected(client, admin):
    uuid = users_collection.find_one({"email": "root@nexora.com"})["user_uuid"]

    def part(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    token = f"{part({'alg': 'none', 'typ': 'JWT'})}.{part({'sub': uuid, 'exp': 4102444800})}."
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_token_without_subject_or_for_deleted_user_is_rejected(client, make_user):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert client.get("/auth/me", headers=bearer(forge({"exp": future}))).status_code == 401

    user, headers = make_user("gone@nexora.com", "IT", "DEVELOPER")
    users_collection.delete_one({"user_uuid": user["user_uuid"]})
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_garbage_authorization_headers_are_rejected(client):
    for value in ("Bearer", "Bearer not.a.jwt", "Basic abc", "bearer "):
        assert client.get("/auth/me", headers={"Authorization": value}).status_code == 401


# ---- one authorisation path: every route is protected ---------------------------------------

def _protected_routes():
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if (method.upper(), path) not in PUBLIC_ROUTES:
                yield method.upper(), path


@pytest.mark.parametrize("method,path", sorted(_protected_routes()))
def test_every_protected_route_rejects_anonymous_callers(client, method, path):
    url = path.replace("{", "").replace("}", "")
    assert client.request(method, url).status_code == 401, f"{method} {path} is reachable without a token"


ADMIN_ONLY = [
    ("GET", "/users"), ("POST", "/users"), ("GET", "/users/x"), ("PUT", "/users/x"), ("DELETE", "/users/x"),
    ("GET", "/audit-logs"), ("GET", "/admin/dashboard"),
    ("POST", "/departments"), ("PUT", "/departments/IT"), ("POST", "/roles"), ("PUT", "/roles/DEVELOPER"),
    ("POST", "/api/documents/scan-folder"), ("POST", "/api/documents/scan-and-ingest"),
    ("POST", "/api/documents/upload"), ("POST", "/api/documents/x/ingest"),
    ("PATCH", "/api/documents/x/access"), ("DELETE", "/api/documents/x"),
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_ordinary_employee_gets_403_on_every_admin_route(client, make_user, method, path):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.request(method, path, headers=dev).status_code == 403


# ---- view-url must not confirm that a document exists ---------------------------------------

def test_view_url_refusal_is_identical_for_missing_and_forbidden_documents(client, make_user, admin):
    add_doc("secret", "restricted", "FIN")
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")

    forbidden = client.get("/api/documents/secret/view-url", headers=dev)
    missing = client.get("/api/documents/nope/view-url", headers=dev)
    assert (forbidden.status_code, forbidden.json()) == (missing.status_code, missing.json()) == (404, {"detail": "Document not found."})

    # Admin permissions grant management, not reading.
    assert client.get("/api/documents/secret/view-url", headers=admin).status_code == 404


# ---- deny by default on odd data -------------------------------------------------------------

def test_documents_with_missing_or_unknown_classification_are_hidden_from_ordinary_users(client, make_user):
    from database.connection import documents_collection

    documents_collection.insert_one({"document_uuid": "u1", "document_name": "no-class"})
    add_doc("weird", "top-secret")
    add_doc("null-access", "confidential", "FIN")
    documents_collection.update_one({"document_uuid": "null-access"}, {"$set": {"access": None}})
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")

    response = client.get("/api/documents/", headers=dev)
    assert response.status_code == 200 and response.json() == []


# ---- chat history isolation ------------------------------------------------------------------

def test_users_only_see_and_delete_their_own_conversations(client, make_user, monkeypatch):
    stub_answering(monkeypatch)
    _, alice = make_user("alice@nexora.com", "IT", "DEVELOPER")
    _, bob = make_user("bob@nexora.com", "IT", "DEVELOPER")

    conversation_id = ask(client, alice).json()["conversation_id"]

    assert client.get("/api/chat/conversations", headers=bob).json() == []
    assert client.get(f"/api/chat/conversations/{conversation_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/chat/conversations/{conversation_id}", headers=bob).status_code in (400, 404)
    assert chat_conversations_collection.count_documents({"conversation_id": conversation_id}) == 1


def test_delete_unknown_conversation_returns_404(client, make_user):
    _, alice = make_user("alice@nexora.com", "IT", "DEVELOPER")
    assert client.delete("/api/chat/conversations/nope", headers=alice).status_code == 404


def test_ask_with_someone_elses_conversation_id_is_a_clean_4xx(client, make_user, monkeypatch):
    stub_answering(monkeypatch)
    _, alice = make_user("alice@nexora.com", "IT", "DEVELOPER")
    _, bob = make_user("bob@nexora.com", "IT", "DEVELOPER")
    conversation_id = ask(client, alice).json()["conversation_id"]

    def boom(*a, **k):
        raise AssertionError("retrieval/LLM must not run for a conversation the caller does not own")

    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", boom)
    monkeypatch.setattr("routes.rag_routes.generate_answer", boom)

    assert ask(client, bob, conversation_id=conversation_id).status_code == 404
    assert ask(client, bob, conversation_id="never-existed").status_code == 404


def test_ask_with_someone_elses_conversation_id_never_writes_into_it(client, make_user, monkeypatch):
    stub_answering(monkeypatch)
    _, alice = make_user("alice@nexora.com", "IT", "DEVELOPER")
    _, bob = make_user("bob@nexora.com", "IT", "DEVELOPER")
    conversation_id = ask(client, alice).json()["conversation_id"]
    before = chat_conversations_collection.find_one({"conversation_id": conversation_id})["messages"]

    lenient = TestClient(app, raise_server_exceptions=False)
    ask(lenient, bob, conversation_id=conversation_id)

    after = chat_conversations_collection.find_one({"conversation_id": conversation_id})["messages"]
    assert after == before


# ---- audit: every query is recorded ----------------------------------------------------------

def test_answered_and_refused_questions_are_both_audited(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    stub_answering(monkeypatch)
    ask(client, dev, "what is the notice period?")

    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", lambda *a, **k: [])
    ask(client, dev, "profit of project x?")

    rows = list(audit_log_collection.find({"action": "rag.ask"}).sort("ts", 1))
    assert [r["target"] for r in rows] == ["what is the notice period?", "profit of project x?"]
    assert rows[1]["after"]["chunks"] == 0


# ---- input validation at the boundary --------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"question": "x" * 2001},
    {"question": ""},
    {"question": "   "},
    {"question": "ok", "conversation_id": 123},
    {},
])
def test_ask_rejects_bad_input_with_422(client, make_user, body):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.post("/api/rag/ask", headers=dev, json=body).status_code == 422


def test_login_with_malformed_email_or_extra_fields_is_422(client):
    assert client.post("/auth/login", json={"email": "not-an-email", "password": "x"}).status_code == 422
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "x", "is_admin": True}).status_code == 422


def test_login_unknown_email_still_pays_the_bcrypt_cost(client, monkeypatch):
    calls = []
    real = __import__("routes.auth_routes", fromlist=["x"]).verify_password
    monkeypatch.setattr("routes.auth_routes.verify_password", lambda p, h: calls.append(h) or real(p, h))

    assert client.post("/auth/login", json={"email": "ghost@nexora.com", "password": PASSWORD}).status_code == 401
    assert len(calls) == 1  # no early exit that would reveal the email does not exist


def test_login_user_without_password_hash_is_a_clean_401(client, make_user):
    user, _ = make_user("broken@nexora.com", "IT", "DEVELOPER")
    users_collection.update_one({"user_uuid": user["user_uuid"]}, {"$unset": {"password_hash": ""}})

    lenient = TestClient(app, raise_server_exceptions=False)
    assert lenient.post("/auth/login", json={"email": "broken@nexora.com", "password": PASSWORD}).status_code == 401


# ---- other confirmed defects ------------------------------------------------------------------

def test_graph_access_update_failure_logs_the_real_error(client, admin, monkeypatch, caplog):
    add_doc("d1", "internal")

    def boom(*args, **kwargs):
        raise RuntimeError("neo4j-is-down")

    monkeypatch.setattr("services.document_service.update_document_access_in_graph", boom)
    r = client.patch("/api/documents/d1/access", headers=admin,
                     json={"department_code": "FIN", "classification": "internal", "access": {}})
    assert r.status_code == 200

    assert "neo4j-is-down" in caplog.text


def test_system_prompt_marks_retrieved_context_as_untrusted_data():
    prompt = llm_service.SYSTEM_PROMPT.lower()
    assert "untrusted" in prompt or "ignore any instructions" in prompt
