"""Access matrix: `can_view` and `build_document_filter` must agree on every case."""

import itertools

import mongomock
import pytest

from services.access.policy import UserContext, build_document_filter, can_view
from services.org_seed import ROLES

DEPARTMENTS = ["HR", "IT", "FIN"]


def ctx(department="IT", role="DEVELOPER", clearance="internal", uuid="u1"):
    return UserContext(uuid, "n", "e@x", department, role, role, clearance, frozenset())


GRANTS = {
    "none": {},
    "user": {"users": ["u1"]},
    "other_user": {"users": ["u2"]},
    "role": {"roles": ["DEVELOPER"]},
    "dept": {"departments": ["IT"]},
}


def cases():
    for classification, owner, grant, clearance in itertools.product(
        ["public", "internal", "confidential", "restricted", None, "bogus"],
        ["IT", "HR", None],
        GRANTS,
        ["internal", "confidential", "restricted"],
    ):
        yield classification, owner, grant, clearance


def expected(classification, owner, grant, clearance):
    if classification in ("public", "internal"):
        return True
    if grant in ("user", "role", "dept"):
        return True
    return classification == "confidential" and clearance != "internal" and owner == "IT"


@pytest.mark.parametrize("classification,owner,grant,clearance", list(cases()))
def test_policy_matrix(classification, owner, grant, clearance):
    doc = {"document_uuid": "d", "department_code": owner, "access": GRANTS[grant]}
    if classification is not None:
        doc["classification"] = classification

    user = ctx(clearance=clearance)
    collection = mongomock.MongoClient().db.docs
    collection.insert_one(dict(doc))

    in_python = can_view(user, doc)
    in_mongo = collection.count_documents(build_document_filter(user)) == 1

    assert in_python == in_mongo, "can_view and build_document_filter disagree"
    assert in_python == expected(classification, owner, grant, clearance)


def test_every_seeded_role_is_covered_by_a_known_clearance():
    assert {c for *_, c, _ in ROLES} <= {"public", "internal", "confidential", "restricted"}
    assert len(ROLES) == 19
