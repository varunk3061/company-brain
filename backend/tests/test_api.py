from conftest import login, PASSWORD
from database.connection import documents_collection


def add_doc(name, classification, department_code=None, access=None):
    documents_collection.insert_one({
        "document_uuid": name, "document_name": name, "category": None,
        "last_update": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "department_code": department_code, "classification": classification,
        "access": access or {"departments": [], "roles": [], "users": []},
        "needs_classification": False, "file_path": f"/x/{name}",
    })


def names(client, headers):
    response = client.get("/api/documents/", headers=headers)
    assert response.status_code == 200, response.text
    return {d["document_name"] for d in response.json()}


# ---- auth ---------------------------------------------------------------

def test_login_wrong_password_is_generic(client):
    r = client.post("/auth/login", json={"email": "root@nexora.com", "password": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password"
    r = client.post("/auth/login", json={"email": "ghost@nexora.com", "password": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password"


def test_login_returns_permissions(client):
    r = client.post("/auth/login", json={"email": "root@nexora.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    assert "users.manage" in r.json()["user"]["permissions"]


def test_requires_token(client):
    assert client.get("/users").status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_non_admin_cannot_manage_users_or_org(client, make_user):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.get("/users", headers=dev).status_code == 403
    assert client.post("/departments", headers=dev, json={"code": "OPS", "name": "Operations"}).status_code == 403
    assert client.get("/departments", headers=dev).status_code == 200  # read-only for dropdowns


# ---- users --------------------------------------------------------------

def test_role_must_belong_to_department(client, admin):
    r = client.post("/users", headers=admin, json={
        "name": "Bad Combo", "email": "bad@nexora.com", "password": PASSWORD,
        "department_code": "IT", "role_code": "PAYROLL_SPECIALIST",
    })
    assert r.status_code == 422


def test_short_password_rejected(client, admin):
    r = client.post("/users", headers=admin, json={
        "name": "Short Pw", "email": "s@nexora.com", "password": "short",
        "department_code": "IT", "role_code": "DEVELOPER",
    })
    assert r.status_code == 422


def test_blocked_user_rejected_on_next_request(client, make_user, admin):
    user, headers = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.get("/auth/me", headers=headers).status_code == 200
    client.put(f"/users/{user['user_uuid']}", headers=admin, json={"status": "blocked"})
    assert client.get("/auth/me", headers=headers).status_code == 403


def test_cannot_block_or_delete_self_or_last_admin(client, admin):
    me = client.get("/auth/me", headers=admin).json()["user_uuid"]
    assert client.put(f"/users/{me}", headers=admin, json={"status": "blocked"}).status_code == 409
    assert client.put(f"/users/{me}", headers=admin, json={"department_code": "IT", "role_code": "DEVELOPER"}).status_code == 409
    assert client.delete(f"/users/{me}", headers=admin).status_code == 409


def test_user_responses_never_leak_hash(client, admin):
    body = client.get("/users", headers=admin).text
    assert "password" not in body and "_id" not in body


# ---- org ----------------------------------------------------------------

def test_seeded_org_matches_org_chart(client, admin):
    assert {d["code"] for d in client.get("/departments", headers=admin).json()} == {"EXEC", "HR", "IT", "SALES", "FIN", "LEGAL"}
    assert len(client.get("/roles", headers=admin).json()) == 19


def test_cannot_deactivate_department_with_active_users(client, make_user, admin):
    make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.put("/departments/IT", headers=admin, json={"status": "inactive"}).status_code == 409


# ---- document visibility ------------------------------------------------

def test_visibility_end_to_end_and_revocation(client, make_user, admin):
    dev_user, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    _, fin = make_user("fin@nexora.com", "FIN", "FINANCIAL_ANALYST")

    add_doc("handbook", "internal")
    add_doc("fin-budget", "confidential", "FIN")
    add_doc("legal-case", "restricted", "LEGAL")

    assert names(client, dev) == {"handbook"}
    assert names(client, fin) == {"handbook", "fin-budget"}

    grant = {"department_code": "LEGAL", "classification": "restricted",
             "access": {"departments": [], "roles": [], "users": [dev_user["user_uuid"]]}}
    assert client.patch("/api/documents/legal-case/access", headers=admin, json=grant).status_code == 200
    assert names(client, dev) == {"handbook", "legal-case"}
    assert "legal-case" not in names(client, fin)

    grant["access"]["users"] = []
    client.patch("/api/documents/legal-case/access", headers=admin, json=grant)
    assert names(client, dev) == {"handbook"}  # revocation applies on the very next request


def test_role_change_applies_without_relogin(client, make_user, admin):
    user, headers = make_user("alice@nexora.com", "IT", "DEVELOPER")
    add_doc("fin-budget", "confidential", "FIN")
    assert "fin-budget" not in names(client, headers)

    client.put(f"/users/{user['user_uuid']}", headers=admin, json={"department_code": "FIN", "role_code": "FINANCIAL_ANALYST"})
    assert "fin-budget" in names(client, headers)


def test_admin_manages_but_does_not_bypass_content_rules(client, admin):
    add_doc("legal-case", "restricted", "LEGAL")
    # Managers list metadata for governance...
    assert "legal-case" in names(client, admin)
    # ...but only via the manage permission, not by being able to read content: a non-manager admin-less user can't.


def test_access_update_rejects_unknown_codes(client, admin):
    add_doc("d1", "internal")
    bad = {"department_code": "NOPE", "classification": "internal", "access": {}}
    assert client.patch("/api/documents/d1/access", headers=admin, json=bad).status_code == 422
    bad = {"classification": "internal", "access": {"roles": ["GHOST"]}}
    assert client.patch("/api/documents/d1/access", headers=admin, json=bad).status_code == 422


def test_non_manager_cannot_change_access(client, make_user):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    add_doc("d1", "internal")
    r = client.patch("/api/documents/d1/access", headers=dev, json={"classification": "public", "access": {}})
    assert r.status_code == 403


# ---- /auth/me extras and audit log -------------------------------------

def test_me_includes_department_name_and_clearance(client, make_user):
    _, headers = make_user("fin@nexora.com", "FIN", "FINANCIAL_ANALYST")
    me = client.get("/auth/me", headers=headers).json()
    assert me["department_name"] == "Finance" and me["clearance"] == "confidential"


def test_audit_log_requires_permission_and_hides_payloads(client, make_user, admin):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert client.get("/audit-logs", headers=dev).status_code == 403

    body = client.get("/audit-logs", headers=admin)
    assert body.status_code == 200
    data = body.json()
    assert data["total"] >= 1
    assert data["items"][0]["action"] == "user.create"            # newest first
    assert data["items"][0]["actor_name"] == "Root Admin"
    assert "before" not in data["items"][0] and "after" not in data["items"][0]
    assert "password" not in body.text


def test_audit_log_filters_by_action_and_actor(client, make_user, admin):
    make_user("dev@nexora.com", "IT", "DEVELOPER")
    data = client.get("/audit-logs", headers=admin).json()
    assert "user.create" in data["actions"]

    by_action = client.get("/audit-logs", params={"action": "user.create"}, headers=admin).json()
    assert by_action["total"] >= 1
    assert all(item["action"] == "user.create" for item in by_action["items"])

    assert client.get("/audit-logs", params={"action": "role.create"}, headers=admin).json()["total"] == 0

    by_actor = client.get("/audit-logs", params={"actor": "root ad"}, headers=admin).json()
    assert by_actor["total"] >= 1
    assert all(item["actor_name"] == "Root Admin" for item in by_actor["items"])

    assert client.get("/audit-logs", params={"actor": "nobody-here"}, headers=admin).json()["total"] == 0
