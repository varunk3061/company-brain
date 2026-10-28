"""Query router: entity detection, which retrieval paths run, graph facts and their permission check.

No live Neo4j is needed: the driver is replaced by small fakes.
"""

import pytest

from database.connection import audit_log_collection, documents_chunk_collection
from services import query_router, retrieval_service
from services.access.policy import UserContext
from services.query_router import RetrievalPlan, build_plan
from test_graph import FakeDriver

DEV = UserContext("u-dev", "Dev", "dev@x", "IT", "DEVELOPER", "Developer", "internal", frozenset())

FAKE_EMBEDDING = lambda: type("E", (), {"embed_query": lambda self, q: [1.0, 0.0]})()


def add_chunk(chunk_uuid, document_uuid, classification, access=None, page=1):
    documents_chunk_collection.insert_one({
        "chunk_uuid": chunk_uuid, "document_uuid": document_uuid, "text": f"text of {chunk_uuid}",
        "source": f"{document_uuid}.pdf", "page": page, "embedding": [1.0, 0.0],
        "classification": classification, "department_code": None,
        "access": access or {"departments": [], "roles": [], "users": []},
    })


CEO_ONLY = {"departments": [], "roles": ["CEO"], "users": []}


# ---- 1. routing rules ------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Who manages Project Atlas?",
    "Which systems does Finance use?",
    "How many projects does the Finance department own?",
    "Who does Ravi report to?",
])
def test_relational_questions(question):
    assert query_router.is_relational(question)


@pytest.mark.parametrize("question", [
    "What is the notice period?",
    "Explain the leave policy",
    "Summarize the dress code",
])
def test_plain_text_questions_are_not_relational(question):
    assert not query_router.is_relational(question)


def test_plan_names_follow_the_rules():
    assert build_plan("What is the notice period?", []).name == "vector"
    assert build_plan("Tell me about Project Atlas", ["project atlas"]).name == "vector+entity"
    assert build_plan("Who manages Project Atlas?", ["project atlas"]).name == "vector+entity+facts"
    assert build_plan("Who manages the budget?", []).use_graph_facts is False  # needs a known entity


# ---- 2. entity detection -----------------------------------------------------------

def test_entity_detection_uses_the_fulltext_index_with_safe_tokens(monkeypatch):
    driver = FakeDriver(read_results=[[{"key": "project atlas"}, {"key": "atlas team"}]])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: driver)

    plan = retrieval_service.plan_retrieval("Who manages Project-Atlas? (urgent!)")

    query, params = driver.tx.calls[0]
    assert "db.index.fulltext.queryNodes" in query
    assert params["index"] == "entity_key_fulltext"
    assert params["search"] == "who OR manages OR project OR atlas OR urgent"  # no Lucene syntax leaks in
    assert plan.entity_keys == ("project atlas",)  # "atlas team" is not in the question
    assert plan.name == "vector+entity+facts"


def test_entity_detection_falls_back_to_a_full_scan_without_the_index(monkeypatch):
    calls = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def run(self, query, **params):
            calls.append(query)
            if "fulltext" in query:
                raise RuntimeError("There is no such fulltext schema index")
            return [{"key": "project atlas"}, {"key": "onecart"}]

    monkeypatch.setattr(retrieval_service, "get_neo4j_driver",
                        lambda: type("D", (), {"session": lambda self, database=None: Session()})())

    plan = retrieval_service.plan_retrieval("Tell me about Project Atlas")

    assert plan.entity_keys == ("project atlas",)
    assert "MATCH (e:Entity) RETURN e.key" in calls[1]


def test_neo4j_down_gives_a_vector_only_plan(monkeypatch):
    def down():
        raise ConnectionError("Neo4j unavailable")

    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", down)

    assert retrieval_service.plan_retrieval("Who manages Project Atlas?").name == "vector"


# ---- 3. retrieval follows the plan ----------------------------------------------------

def test_entity_graph_runs_even_when_vector_search_finds_nothing(client, monkeypatch):
    add_chunk("open", "d-open", "internal")
    add_chunk("ceo-only", "d-ceo", "restricted", access=CEO_ONLY)
    driver = FakeDriver(read_results=[[{"chunk_uuid": "ceo-only"}, {"chunk_uuid": "open"}]])

    monkeypatch.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    monkeypatch.setattr(retrieval_service, "_vector_search", lambda **kw: [])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: driver)

    plan = RetrievalPlan(entity_keys=("project atlas",), relational=False)
    result = retrieval_service.retrieve_relevant_chunks("Tell me about Project Atlas", DEV, plan=plan)

    assert [c["chunk_uuid"] for c in result] == ["open"]  # restricted one still filtered by MongoDB
    _, params = driver.tx.calls[0]
    assert params["keys"] == ["project atlas"]  # keys came from the plan, not detected again


def test_vector_only_plan_does_not_query_the_entity_graph(client, monkeypatch):
    def no_neo4j():
        raise AssertionError("entity graph must not run for a vector-only plan")

    monkeypatch.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    monkeypatch.setattr(retrieval_service, "_vector_search",
                        lambda **kw: [{"chunk_uuid": "v1", "document_uuid": "d1", "text": "t", "score": 0.8}])
    monkeypatch.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", no_neo4j)

    result = retrieval_service.retrieve_relevant_chunks("What is the notice period?", DEV, plan=RetrievalPlan())

    assert [c["chunk_uuid"] for c in result] == ["v1"]


def test_nothing_from_any_path_returns_empty(client, monkeypatch):
    monkeypatch.setattr(retrieval_service, "get_embedding", FAKE_EMBEDDING)
    monkeypatch.setattr(retrieval_service, "_vector_search", lambda **kw: [])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: FakeDriver(read_results=[[]]))

    plan = RetrievalPlan(entity_keys=("project atlas",))
    assert retrieval_service.retrieve_relevant_chunks("Project Atlas?", DEV, plan=plan) == []


# ---- 4. graph facts (red-team: never from a chunk the user cannot read) ---------------

def test_graph_facts_are_skipped_for_non_relational_plans(monkeypatch):
    def no_neo4j():
        raise AssertionError("facts must not be queried")

    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", no_neo4j)

    assert retrieval_service.retrieve_graph_facts(RetrievalPlan(entity_keys=("x y z",)), DEV) == []
    assert retrieval_service.retrieve_graph_facts(RetrievalPlan(relational=True), DEV) == []


def test_graph_facts_keep_only_permitted_evidence_and_are_cited(client, monkeypatch):
    add_chunk("open", "d-open", "internal", page=4)
    add_chunk("ceo-only", "d-ceo", "restricted", access=CEO_ONLY)
    driver = FakeDriver(read_results=[[
        {"subject": "Ravi Kumar", "relation": "MANAGES", "object": "Project Atlas", "chunk_uuid": "open"},
        {"subject": "Ravi Kumar", "relation": "MANAGES", "object": "Project Atlas", "chunk_uuid": "open"},
        {"subject": "Project Atlas", "relation": "OWNS", "object": "Secret Budget", "chunk_uuid": "ceo-only"},
        {"subject": "Project Atlas", "relation": "USES", "object": "Ghost", "chunk_uuid": "missing"},
    ]])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: driver)

    facts = retrieval_service.retrieve_graph_facts(
        RetrievalPlan(entity_keys=("project atlas",), relational=True), DEV)

    assert facts == [{
        "subject": "Ravi Kumar", "relation": "MANAGES", "object": "Project Atlas",
        "chunk_uuid": "open", "document_uuid": "d-open", "source": "d-open.pdf", "page": 4,
    }]


def test_graph_facts_survive_neo4j_failure(client, monkeypatch):
    def down():
        raise ConnectionError("Neo4j unavailable")

    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", down)

    plan = RetrievalPlan(entity_keys=("project atlas",), relational=True)
    assert retrieval_service.retrieve_graph_facts(plan, DEV) == []


# ---- 5. /api/rag/ask uses the router ----------------------------------------------------

FACT = {"subject": "Ravi Kumar", "relation": "MANAGES", "object": "Project Atlas", "chunk_uuid": "c9",
        "document_uuid": "d9", "source": "Org.pdf", "page": 2}

CHUNK = {"chunk_uuid": "c1", "text": "Project Atlas launched in 2025.", "source": "Atlas.pdf", "page": 1,
         "document_uuid": "d1"}


def setup_route(monkeypatch, plan, chunks, facts):
    seen = {}

    def fake_retrieve(question, ctx, limit=10, plan=None, **kwargs):
        seen["plan"] = plan
        return chunks

    def fake_llm(question, context):
        seen["context"] = context
        return "Ravi Kumar manages Project Atlas."

    monkeypatch.setattr("routes.rag_routes.plan_retrieval", lambda q: plan)
    monkeypatch.setattr("routes.rag_routes.retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr("routes.rag_routes.retrieve_graph_facts", lambda p, ctx: facts)
    monkeypatch.setattr("routes.rag_routes.generate_answer", fake_llm)
    return seen


def test_relationship_question_sends_facts_to_the_llm_and_cites_them(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    plan = RetrievalPlan(entity_keys=("project atlas",), relational=True)
    seen = setup_route(monkeypatch, plan, [CHUNK], [FACT])

    r = client.post("/api/rag/ask", headers=dev, json={"question": "Who manages Project Atlas?"})

    assert r.status_code == 200
    assert seen["plan"] is plan  # entities detected once, shared with chunk retrieval
    assert "- Ravi Kumar MANAGES Project Atlas (Source: Org.pdf, Page: 2)" in seen["context"]
    assert r.json()["sources"] == [
        {"source": "Atlas.pdf", "page": 1, "document_uuid": "d1"},
        {"source": "Org.pdf", "page": 2, "document_uuid": "d9"},
    ]
    after = audit_log_collection.find_one({"action": "rag.ask"})["after"]
    assert after["route"] == "vector+entity+facts" and after["graph_facts"] == 1


def test_facts_alone_are_enough_to_answer(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    plan = RetrievalPlan(entity_keys=("project atlas",), relational=True)
    setup_route(monkeypatch, plan, [], [FACT])

    r = client.post("/api/rag/ask", headers=dev, json={"question": "Who manages Project Atlas?"})

    assert r.json()["answer"] == "Ravi Kumar manages Project Atlas."
    assert r.json()["sources"] == [{"source": "Org.pdf", "page": 2, "document_uuid": "d9"}]


def test_a_graph_fact_prevents_a_low_rerank_abstain(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    monkeypatch.setattr("services.rerank_service.RERANK_MIN_SCORE", 0.5)
    weak = {**CHUNK, "rerank_score": 0.01, "rerank_provider": "local"}
    setup_route(monkeypatch, RetrievalPlan(entity_keys=("project atlas",), relational=True), [weak], [FACT])

    r = client.post("/api/rag/ask", headers=dev, json={"question": "Who manages Project Atlas?"})

    assert r.json()["answer"] == "Ravi Kumar manages Project Atlas."


def test_plain_question_keeps_the_old_answer_shape(client, make_user, monkeypatch):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    seen = setup_route(monkeypatch, RetrievalPlan(), [CHUNK], [])

    r = client.post("/api/rag/ask", headers=dev, json={"question": "When did Atlas launch?"})

    assert r.json()["sources"] == [{"source": "Atlas.pdf", "page": 1, "document_uuid": "d1"}]
    assert "Knowledge-graph facts" not in seen["context"]
    assert audit_log_collection.find_one({"action": "rag.ask"})["after"]["route"] == "vector"
