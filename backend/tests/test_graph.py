"""Entity graph: extraction, Neo4j writes, delete clean-up and the no-leak rule for entity retrieval.

No live Groq or Neo4j is needed: both are replaced by small fakes.
"""

import json

from database.connection import documents_chunk_collection
from services import entity_service, graph_service, retrieval_service
from services.access.policy import UserContext

DEV = UserContext("u-dev", "Dev", "dev@x", "IT", "DEVELOPER", "Developer", "internal", frozenset())


# ---- fakes ----------------------------------------------------------------------

class FakeTx:
    """Records every Cypher query and its parameters."""

    def __init__(self):
        self.calls = []

    def run(self, query, **params):
        self.calls.append((" ".join(query.split()), params))
        return self

    def consume(self):
        return None


class FakeSession:
    def __init__(self, tx, read_results=None):
        self.tx = tx
        self.read_results = list(read_results or [])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute_write(self, work):
        return work(self.tx)

    def run(self, query, **params):
        # Read queries (retrieval) return the next prepared result.
        self.tx.calls.append((" ".join(query.split()), params))
        return self.read_results.pop(0) if self.read_results else []


class FakeDriver:
    def __init__(self, read_results=None):
        self.tx = FakeTx()
        self.read_results = read_results

    def session(self, database=None):
        return FakeSession(self.tx, self.read_results)


def queries_with(tx, text):
    return [(q, p) for q, p in tx.calls if text in q]


# ---- 1. extraction (entity_service) --------------------------------------------

def test_parse_maps_short_ids_and_drops_bad_items():
    reply = json.dumps({"chunks": [
        {
            "chunk_uuid": "1",
            "entities": [
                {"name": "Finance Dept.", "type": "Department"},
                {"name": "Project Atlas", "type": "Project"},
                {"name": "Something", "type": "Planet"},  # type not allowed
            ],
            "relations": [
                {"from": "finance dept", "type": "OWNS", "to": "Project Atlas"},
                {"from": "Finance Dept.", "type": "HATES", "to": "Project Atlas"},  # relation not allowed
                {"from": "Finance Dept.", "type": "OWNS", "to": "Unknown Thing"},   # end not an entity
            ],
        },
        {"chunk_uuid": "9", "entities": [{"name": "Ghost", "type": "Person"}]},  # id we never sent
    ]})

    entities, relations = entity_service._parse_response(f"```json\n{reply}\n```", {"1": "chunk-a"})

    assert {(e["key"], e["type"], e["chunk_uuid"]) for e in entities} == {
        ("finance dept", "Department", "chunk-a"),
        ("project atlas", "Project", "chunk-a"),
    }
    assert relations == [
        {"from_key": "finance dept", "to_key": "project atlas", "type": "OWNS", "chunk_uuid": "chunk-a"},
    ]


def test_extraction_batches_chunks_and_survives_a_failed_batch(monkeypatch):
    calls = []

    class FakeLLM:
        def invoke(self, messages):
            calls.append(messages)
            if len(calls) <= 2:  # first batch fails twice (both attempts)
                raise RuntimeError("rate limited")
            return type("R", (), {"content": json.dumps({"chunks": [
                {"chunk_uuid": "1", "entities": [{"name": "OneCart", "type": "Client"}], "relations": []},
            ]})})()

    monkeypatch.setattr(entity_service, "_get_groq_llm", lambda: FakeLLM())
    monkeypatch.setattr(entity_service.time, "sleep", lambda s: None)

    chunks = [{"chunk_uuid": f"c{i}", "text": f"text {i}"} for i in range(7)]  # 5 + 2 -> 2 batches
    result = entity_service.extract_from_chunks(chunks)

    assert len(calls) == 3  # batch 1: 2 failed attempts, batch 2: 1 call
    assert result["entities"] == [{"key": "onecart", "name": "OneCart", "type": "Client", "chunk_uuid": "c5"}]


# ---- 2. writing to Neo4j (graph_service) ---------------------------------------

DOCUMENT = {
    "document_uuid": "d1", "document_name": "Policy.pdf", "file_hash": "h1",
    "department_code": "HR", "classification": "internal",
    "access": {"departments": [], "roles": [], "users": []},
}
CHUNKS = [{"chunk_uuid": "c1", "text": "Finance owns Project Atlas.", "source": "Policy.pdf", "page": 1}]
GRAPH = {
    "entities": [
        {"key": "finance", "name": "Finance", "type": "Department", "chunk_uuid": "c1"},
        {"key": "project atlas", "name": "Project Atlas", "type": "Project", "chunk_uuid": "c1"},
    ],
    "relations": [{"from_key": "finance", "to_key": "project atlas", "type": "OWNS", "chunk_uuid": "c1"}],
}


def test_sync_writes_entities_and_relations_with_evidence(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(graph_service, "get_neo4j_driver", lambda: driver)
    monkeypatch.setattr(graph_service, "_load_saved_entities", lambda *a: None)
    monkeypatch.setattr(graph_service, "extract_from_chunks", lambda chunks: GRAPH)

    graph_service.sync_document_to_graph(DOCUMENT, CHUNKS)

    [(_, mention_params)] = queries_with(driver.tx, "MERGE (c)-[:MENTIONS]->(e)")
    assert mention_params["entities"] == GRAPH["entities"]

    [(_, relation_params)] = queries_with(driver.tx, "MERGE (a)-[r:RELATED_TO")
    assert relation_params["relations"] == GRAPH["relations"]
    assert relation_params["document_uuid"] == "d1"  # evidence for clean-up

    # Old relations of this document are removed before new ones are written.
    assert queries_with(driver.tx, "MATCH ()-[r:RELATED_TO {document_uuid: $document_uuid}]->() DELETE r")


def test_unchanged_pdf_reuses_saved_entities_without_calling_groq(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(graph_service, "get_neo4j_driver", lambda: driver)
    monkeypatch.setattr(graph_service, "_load_saved_entities", lambda *a: GRAPH)

    def boom(chunks):
        raise AssertionError("Groq must not be called for an unchanged PDF")

    monkeypatch.setattr(graph_service, "extract_from_chunks", boom)

    graph_service.sync_document_to_graph(DOCUMENT, CHUNKS)

    [(_, mention_params)] = queries_with(driver.tx, "MERGE (c)-[:MENTIONS]->(e)")
    assert mention_params["entities"] == GRAPH["entities"]


def test_delete_removes_relations_document_and_only_unused_entities(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(graph_service, "get_neo4j_driver", lambda: driver)

    graph_service.delete_document_from_graph("d1")

    queries = [q for q, _ in driver.tx.calls]

    # Exact label/type spelling matters: a typo matches nothing and Neo4j raises no error.
    assert any("MATCH ()-[r:RELATED_TO {document_uuid: $document_uuid}]->() DELETE r" in q for q in queries)
    assert any("DETACH DELETE c, d" in q for q in queries)
    assert any("WHERE NOT (e)<-[:MENTIONS]-(:Chunk) DETACH DELETE e" in q for q in queries)

    [(_, params)] = queries_with(driver.tx, "RELATED_TO {document_uuid")
    assert params["document_uuid"] == "d1"


# ---- 3. retrieval: entity matching ---------------------------------------------

def test_entity_names_match_whole_words_only(monkeypatch):
    driver = FakeDriver(read_results=[
        [{"key": "project atlas"}, {"key": "hr"}, {"key": "atlas"}, {"key": "onecart"}],
        [{"chunk_uuid": "c1"}],
    ])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: driver)

    result = retrieval_service._find_entity_chunk_uuids("Who manages Project Atlas? (not atlases)")

    assert result == ["c1"]
    _, params = driver.tx.calls[1]
    # "hr" is too short; "onecart" is not in the question; "atlas" matches as a whole word.
    assert sorted(params["keys"]) == ["atlas", "project atlas"]


def test_no_entity_in_question_skips_the_chunk_query(monkeypatch):
    driver = FakeDriver(read_results=[[{"key": "onecart"}]])
    monkeypatch.setattr(retrieval_service, "get_neo4j_driver", lambda: driver)

    assert retrieval_service._find_entity_chunk_uuids("What is the leave policy?") == []
    assert len(driver.tx.calls) == 1


# ---- 4. red-team: entity retrieval must not leak --------------------------------

def add_chunk(chunk_uuid, document_uuid, classification, department_code=None, access=None, embedding=None):
    documents_chunk_collection.insert_one({
        "chunk_uuid": chunk_uuid, "document_uuid": document_uuid, "text": f"text of {chunk_uuid}",
        "source": f"{document_uuid}.pdf", "page": 1, "embedding": embedding or [1.0, 0.0],
        "classification": classification, "department_code": department_code,
        "access": access or {"departments": [], "roles": [], "users": []},
    })


def test_entity_chunks_from_documents_the_user_cannot_see_are_dropped(client):
    add_chunk("open", "d-open", "internal")
    add_chunk("fin-secret", "d-fin", "confidential", department_code="FIN")
    add_chunk("ceo-only", "d-ceo", "restricted", access={"departments": [], "roles": ["CEO"], "users": []})

    chunks = retrieval_service._load_entity_chunks(["open", "fin-secret", "ceo-only"], DEV, [1.0, 0.0])

    assert [c["chunk_uuid"] for c in chunks] == ["open"]
    assert "embedding" not in chunks[0]  # raw vectors never leave retrieval


def test_entity_chunks_from_a_granted_document_are_returned(client):
    add_chunk("granted", "d-g", "restricted", access={"departments": ["IT"], "roles": [], "users": []})

    chunks = retrieval_service._load_entity_chunks(["granted"], DEV, [1.0, 0.0])

    assert [c["chunk_uuid"] for c in chunks] == ["granted"]


def test_entity_chunk_score_uses_the_vector_search_scale(client):
    add_chunk("same", "d1", "internal", embedding=[1.0, 0.0])
    add_chunk("opposite", "d2", "internal", embedding=[-1.0, 0.0])

    scores = {c["chunk_uuid"]: c["score"] for c in
              retrieval_service._load_entity_chunks(["same", "opposite"], DEV, [1.0, 0.0])}

    assert scores == {"same": 1.0, "opposite": 0.0}  # (1 + cosine) / 2, like Atlas cosine


def test_full_retrieval_never_returns_a_restricted_entity_chunk(client, monkeypatch):
    add_chunk("open", "d-open", "internal")
    add_chunk("ceo-only", "d-ceo", "restricted", access={"departments": [], "roles": ["CEO"], "users": []})

    monkeypatch.setattr(retrieval_service, "get_embedding",
                        lambda: type("E", (), {"embed_query": lambda self, q: [1.0, 0.0]})())
    monkeypatch.setattr(retrieval_service, "_vector_search",
                        lambda **kw: [{"chunk_uuid": "open", "document_uuid": "d-open", "text": "t", "score": 0.9}])
    monkeypatch.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])
    # The graph points at both chunks; only MongoDB decides what the user may read.
    monkeypatch.setattr(retrieval_service, "_find_entity_chunk_uuids", lambda q: ["ceo-only", "open"])

    result = retrieval_service.retrieve_relevant_chunks("Who manages Project Atlas?", DEV)

    assert [c["chunk_uuid"] for c in result] == ["open"]


def test_neo4j_down_still_answers_from_vector_search(client, monkeypatch):
    monkeypatch.setattr(retrieval_service, "get_embedding",
                        lambda: type("E", (), {"embed_query": lambda self, q: [1.0, 0.0]})())
    monkeypatch.setattr(retrieval_service, "_vector_search",
                        lambda **kw: [{"chunk_uuid": "v1", "document_uuid": "d1", "text": "t", "score": 0.8}])
    monkeypatch.setattr(retrieval_service, "_find_related_document_uuids", lambda seeds: [])

    def neo4j_down(question):
        raise ConnectionError("Neo4j unavailable")

    monkeypatch.setattr(retrieval_service, "_find_entity_chunk_uuids", neo4j_down)

    result = retrieval_service.retrieve_relevant_chunks("Who manages Project Atlas?", DEV)

    assert [c["chunk_uuid"] for c in result] == ["v1"]
