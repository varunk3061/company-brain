import os

# Must be set before any app module is imported.
os.environ.update({
    "MONGODB_URI": "mongomock://test",
    "DATABASE_NAME": "company_brain_test",
    "JWT_SECRET_KEY": "x" * 48,
    "ADMIN_NAME": "Root Admin",
    "ADMIN_EMAIL": "root@nexora.com",
    "ADMIN_PASSWORD": "correct-horse-battery",
    # No cross-encoder download in tests; rerank tests switch it on with a fake scorer.
    "RERANK_PROVIDER": "none",
    # Never reach a real Neo4j from tests (load_dotenv does not override this); graph tests use fakes.
    "NEO4J_PASSWORD": "",
})

import pytest
from fastapi.testclient import TestClient

import main
from database.connection import db
from main import app

# Tests never need a live Neo4j: graph sync is an enhancement and is faked where a test needs it.
main.verify_neo4j_connection = lambda: True
main.initialize_graph = lambda: None

PASSWORD = "a-long-test-password"


@pytest.fixture()
def client():
    for name in db.list_collection_names():
        db.drop_collection(name)
    with TestClient(app) as test_client:  # runs lifespan: indexes, org seed, bootstrap admin
        yield test_client


def login(client, email, password=PASSWORD):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "root@nexora.com", "correct-horse-battery")


@pytest.fixture()
def make_user(client, admin):
    def _make(email, department_code, role_code):
        response = client.post("/users", headers=admin, json={
            "name": email.split("@")[0], "email": email, "password": PASSWORD,
            "department_code": department_code, "role_code": role_code,
        })
        assert response.status_code == 201, response.text
        return response.json(), login(client, email)
    return _make
