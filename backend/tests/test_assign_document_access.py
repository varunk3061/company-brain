"""scripts/assign_document_access.py: manifest rows -> owner department, classification and grants."""

import csv
from uuid import uuid4

from database.connection import audit_log_collection, documents_chunk_collection, documents_collection
from scripts import assign_document_access as script

FIELDS = ["doc_id", "filename", "department", "classification", "allowed_roles", "allowed_user_ids", "project_ids"]


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _doc(name):
    uuid = str(uuid4())
    documents_collection.insert_one({
        "document_uuid": uuid, "document_name": name, "classification": "internal",
        "department_code": None, "access": {"departments": [], "roles": [], "users": []},
        "needs_classification": True,
    })
    documents_chunk_collection.insert_one({
        "chunk_uuid": str(uuid4()), "document_uuid": uuid, "classification": "internal",
        "access": {"departments": [], "roles": [], "users": []}, "allowed_roles": ["stale"],
    })
    return uuid


def _setup(tmp_path, make_user, manifest_rows):
    karan, _ = make_user("karan.joshi@nexora-tech.example", "IT", "DEVELOPER")
    users = _write_csv(tmp_path / "users.csv", ["user_id", "email"],
                       [{"user_id": "U06", "email": "karan.joshi@nexora-tech.example"}])
    manifest = _write_csv(tmp_path / "manifest.csv", FIELDS,
                          [{k: r.get(k, "") for k in FIELDS} for r in manifest_rows])
    return karan, manifest, users


def test_apply_assigns_department_classification_roles_and_users(client, make_user, tmp_path):
    offer = _doc("HR-OFR-221_Offer_Letter_Karan_Joshi.pdf")
    policy = _doc("FIN-POL-003_Travel_and_Reimbursement_Policy_v2.0.pdf")
    board = _doc("LDR-BRD-Q2FY27_Board_Update_Notes.pdf")
    other = _doc("unrelated.pdf")
    karan, manifest, users = _setup(tmp_path, make_user, [
        {"filename": "HR-OFR-221_Offer_Letter_Karan_Joshi.pdf", "department": "HR",
         "classification": "confidential", "allowed_user_ids": "U06",
         "allowed_roles": "HR Business Partner|HR Operations Specialist|CEO / Admin"},
        {"filename": "FIN-POL-003_Travel_and_Reimbursement_Policy_v2.0.pdf", "department": "Finance",
         "classification": "internal", "allowed_roles": "ALL"},
        {"filename": "ldr-brd-q2fy27_board_update_notes.PDF", "department": "Leadership / Administration",
         "classification": "internal", "allowed_roles": "ALL"},
    ])

    script.main(apply=True, manifest_path=manifest, users_path=users)

    doc = documents_collection.find_one({"document_uuid": offer})
    assert doc["department_code"] == "HR" and doc["classification"] == "confidential"
    assert doc["access"] == {"departments": [], "roles": ["HR_BUSINESS_PARTNER", "HR_OPERATIONS", "CEO"],
                             "users": [karan["user_uuid"]]}
    assert doc["needs_classification"] is False

    chunk = documents_chunk_collection.find_one({"document_uuid": offer})
    assert chunk["classification"] == "confidential" and chunk["access"] == doc["access"]
    assert chunk["allowed_roles"] == doc["access"]["roles"]

    assert documents_collection.find_one({"document_uuid": policy})["department_code"] == "FIN"
    assert documents_collection.find_one({"document_uuid": board})["department_code"] == "EXEC"
    assert documents_collection.find_one({"document_uuid": other})["needs_classification"] is True
    assert audit_log_collection.count_documents({"action": "document.access.update", "actor_uuid": None}) == 3

    # Re-running changes nothing.
    script.main(apply=True, manifest_path=manifest, users_path=users)
    assert audit_log_collection.count_documents({"action": "document.access.update"}) == 3


def test_dry_run_writes_nothing(client, make_user, tmp_path):
    uuid = _doc("A.pdf")
    _, manifest, users = _setup(tmp_path, make_user, [
        {"filename": "A.pdf", "department": "IT", "classification": "restricted", "allowed_roles": "DevOps Engineer"},
    ])

    script.main(apply=False, manifest_path=manifest, users_path=users)

    assert documents_collection.find_one({"document_uuid": uuid})["classification"] == "internal"


def test_unknown_role_or_user_is_not_applied(client, make_user, tmp_path):
    bad_role = _doc("A.pdf")
    bad_user = _doc("B.pdf")
    _, manifest, users = _setup(tmp_path, make_user, [
        {"filename": "A.pdf", "department": "IT", "classification": "restricted", "allowed_roles": "Astronaut"},
        {"filename": "B.pdf", "department": "IT", "classification": "restricted",
         "allowed_roles": "DevOps Engineer", "allowed_user_ids": "U99"},
    ])

    script.main(apply=True, manifest_path=manifest, users_path=users)

    for uuid in (bad_role, bad_user):
        assert documents_collection.find_one({"document_uuid": uuid})["classification"] == "internal"


def test_all_on_a_confidential_document_grants_every_department(client, make_user, tmp_path):
    uuid = _doc("A.pdf")
    _, manifest, users = _setup(tmp_path, make_user, [
        {"filename": "A.pdf", "department": "Sales", "classification": "confidential", "allowed_roles": "ALL"},
    ])

    script.main(apply=True, manifest_path=manifest, users_path=users)

    doc = documents_collection.find_one({"document_uuid": uuid})
    assert set(doc["access"]["departments"]) == {"EXEC", "HR", "IT", "SALES", "FIN", "LEGAL"}
    assert doc["access"]["roles"] == []
