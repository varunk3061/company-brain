# Finds matching chunks with MongoDB Vector Search plus Neo4j, and returns only the ones the user is allowed to see.

import logging
import re

from collections import defaultdict

from fastapi import HTTPException

from database.connection import documents_chunk_collection
from database.neo4j_connection import (
    get_neo4j_driver,
    NEO4J_DATABASE,
)
from services.access.policy import (
    UserContext,
    build_document_filter,
)
from services import rerank_service
from services.embedding_service import get_embedding
from services.graph_service import ENTITY_FULLTEXT_INDEX
from services.query_router import RetrievalPlan, build_plan

logger = logging.getLogger(__name__)


# Must exactly match the Atlas Vector Search index name.
VECTOR_INDEX_NAME = "vector_index"

# Maximum number of additional documents discovered through Neo4j.
MAX_GRAPH_DOCUMENTS = 10

# Maximum number of chunks found through entity matching.
MAX_ENTITY_CHUNKS = 15

# Entity candidates read from the full-text index before the whole-word check.
MAX_ENTITY_CANDIDATES = 200

# Graph relations read from Neo4j, and how many permitted ones reach the LLM.
MAX_GRAPH_FACT_CANDIDATES = 100
MAX_GRAPH_FACTS = 15


def _vector_search(
    question_embedding: list,
    ctx: UserContext,
    candidate_limit: int = 30,
    document_uuids: list | None = None,
) -> list:
    """
    Search MongoDB for relevant chunks.

    If document_uuids is provided, search only those documents.
    Permissions are enforced inside every vector search query.
    """

    permission_filter = build_document_filter(ctx)

    search_filter = permission_filter

    if document_uuids:
        search_filter = {
            "$and": [
                permission_filter,
                {"document_uuid": {"$in": document_uuids}},
            ]
        }

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": question_embedding,
                "numCandidates": 100,
                "limit": candidate_limit,
                "filter": search_filter,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_uuid": 1,
                "text": 1,
                "source": 1,
                "page": 1,
                "document_uuid": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    return list(documents_chunk_collection.aggregate(pipeline))

def _keyword_search(
    question: str,
    ctx: UserContext,
    candidate_limit: int = 30,
    document_uuids: list | None = None,
) -> list:
    """Search MongoDB for chunks matching keywords in the question.

    Permissions are strictly enforced inside the query filter.
    """
    permission_filter = build_document_filter(ctx)
    clauses = [permission_filter, {"$text": {"$search": question}}]

    if document_uuids:
        clauses.append({"document_uuid": {"$in": document_uuids}})

    query = {"$and": clauses}
    projection = {
        "_id": 0,
        "chunk_uuid": 1,
        "text": 1,
        "source": 1,
        "page": 1,
        "document_uuid": 1,
        "score": {"$meta": "textScore"},
    }

    try:
        return list(
            documents_chunk_collection.find(query, projection)
            .sort([("score", {"$meta": "textScore"})])
            .limit(candidate_limit)
        )
    except Exception as exc:
        logger.warning("Keyword text search unavailable (%s): %s", type(exc).__name__, exc)
        return []


def _reciprocal_rank_fusion(
    vector_chunks: list,
    keyword_chunks: list,
    k: int = 60,
) -> list:
    """Combine vector and keyword results using Reciprocal Rank Fusion (RRF).

    Formula: RRF_score = sum(1 / (k + rank))
    Normalizes differing score scales and prioritizes items appearing in both.
    """
    scores = defaultdict(float)
    chunks_by_id = {}

    for rank, chunk in enumerate(vector_chunks, start=1):
        cid = chunk.get("chunk_uuid")
        if cid:
            scores[cid] += 1.0 / (k + rank)
            chunks_by_id[cid] = chunk

    for rank, chunk in enumerate(keyword_chunks, start=1):
        cid = chunk.get("chunk_uuid")
        if cid:
            scores[cid] += 1.0 / (k + rank)
            if cid not in chunks_by_id:
                chunks_by_id[cid] = chunk

    fused = []
    for cid, rrf_score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        item = dict(chunks_by_id[cid])
        item["score"] = rrf_score
        fused.append(item)

    return fused

# Added to pick right chunks
def _fuse_ranked_lists(*ranked_lists, k: int = 60) -> list:
    """RRF over any number of ranked lists, so vector, keyword, topic-graph and
    entity-graph chunks are all scored on the same scale before selection."""
    scores = defaultdict(float)
    chunks_by_id = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            cid = chunk.get("chunk_uuid")
            if not cid:
                continue
            scores[cid] += 1.0 / (k + rank)
            chunks_by_id.setdefault(cid, chunk)

    return [
        {**chunks_by_id[cid], "score": score}
        for cid, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]


def _find_related_document_uuids(seed_document_uuids: list) -> list:
    """
    Ask Neo4j for documents sharing topics with the seed documents.

    Only document IDs are returned. Document content is retrieved
    separately from MongoDB with the user's permission filter.
    """

    if not seed_document_uuids:
        return []

    driver = get_neo4j_driver()

    query = """
    MATCH (seed:Document)-[:HAS_TOPIC]->(t:Topic)
      <-[:HAS_TOPIC]-(related:Document)
      WHERE seed.document_uuid IN $seed_ids
      WITH DISTINCT related, $seed_ids AS seed_ids
      WHERE NOT related.document_uuid IN seed_ids
      RETURN related.document_uuid AS document_uuid
      LIMIT $max_documents
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(
            query,
            seed_ids=seed_document_uuids,
            max_documents=MAX_GRAPH_DOCUMENTS,
        )
        return [
            record["document_uuid"]
            for record in records
            if record.get("document_uuid")
        ]


def _normalize_text(text: str) -> str:
    """Lowercase, keep letters/digits only, pad with spaces so we match whole words."""
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


def _question_tokens(question: str) -> list:
    """Distinct words of the question (letters/digits only), safe to put in a Lucene query."""
    words = _normalize_text(question).split()
    return list(dict.fromkeys(word for word in words if len(word) >= 2))[:64]


def _detect_entity_keys(session, question: str) -> list:
    """
    Entity keys whose name appears in the question as whole words.

    The full-text index narrows the candidates; without it (older graph, index
    still building) every key is scanned as before. Keys shorter than 3
    characters are skipped (too many false matches).
    """

    question_text = _normalize_text(question)
    tokens = _question_tokens(question)

    if not tokens:
        return []

    try:
        records = list(session.run(
            """
            CALL db.index.fulltext.queryNodes($index, $search) YIELD node, score
            RETURN node.key AS key
            ORDER BY score DESC
            LIMIT $limit
            """,
            index=ENTITY_FULLTEXT_INDEX,
            search=" OR ".join(tokens),
            limit=MAX_ENTITY_CANDIDATES,
        ))
    except Exception as exc:
        logger.warning("Entity full-text index unavailable (%s); scanning all entity keys.", type(exc).__name__)
        records = list(session.run("MATCH (e:Entity) RETURN e.key AS key"))

    return list(dict.fromkeys(
        record["key"]
        for record in records
        if record["key"]
        and len(record["key"]) >= 3
        and _normalize_text(record["key"]) in question_text
    ))


def _entity_chunk_uuids_for_keys(session, keys: list) -> list:
    """Chunks mentioning these entities or their direct neighbours (IDs only)."""

    records = session.run(
        """
        MATCH (e:Entity) WHERE e.key IN $keys
        OPTIONAL MATCH (e)-[:RELATED_TO]-(n:Entity)
        WITH collect(DISTINCT e) + collect(DISTINCT n) AS entities
        UNWIND entities AS ent
        MATCH (c:Chunk)-[:MENTIONS]->(ent)
        RETURN DISTINCT c.chunk_uuid AS chunk_uuid
        LIMIT $max_chunks
        """,
        keys=list(keys),
        max_chunks=MAX_ENTITY_CHUNKS,
    )

    return [record["chunk_uuid"] for record in records if record["chunk_uuid"]]


def _find_entity_chunk_uuids(question: str) -> list:
    """
    Ask Neo4j for chunks that mention entities named in the question,
    or entities directly related to them.

    Only chunk IDs are returned. Content is loaded from MongoDB
    with the user's permission filter.
    """

    driver = get_neo4j_driver()

    with driver.session(database=NEO4J_DATABASE) as session:
        keys = _detect_entity_keys(session, question)

        if not keys:
            return []

        return _entity_chunk_uuids_for_keys(session, keys)


def plan_retrieval(question: str) -> RetrievalPlan:
    """
    Detect entities in the question and choose the retrieval paths.

    Never raises: if Neo4j is unavailable the plan is vector-only.
    """

    try:
        driver = get_neo4j_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            keys = _detect_entity_keys(session, question)
    except Exception as exc:
        logger.warning("Entity detection unavailable, using vector-only plan: %s: %s", type(exc).__name__, exc)
        keys = []

    return build_plan(question, keys)


def _find_graph_facts(keys: list) -> list:
    """Relations touching the question's entities, with their evidence chunk (no permission check yet)."""

    driver = get_neo4j_driver()

    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(
            """
            MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
            WHERE a.key IN $keys OR b.key IN $keys
            RETURN a.name AS subject, r.type AS relation, b.name AS object,
                   r.chunk_uuid AS chunk_uuid
            LIMIT $limit
            """,
            keys=list(keys),
            limit=MAX_GRAPH_FACT_CANDIDATES,
        )
        return [dict(record) for record in records]


def retrieve_graph_facts(plan: RetrievalPlan, ctx: UserContext) -> list:
    """
    Graph relations for relationship questions, e.g. "Ravi Kumar MANAGES Project Atlas".

    A fact is kept only if its evidence chunk passes the user's permission
    filter in MongoDB, and it is cited with that chunk's document and page.
    Never raises: facts are an enhancement on top of document retrieval.
    """

    if not plan.use_graph_facts:
        return []

    try:
        candidates = [
            fact for fact in _find_graph_facts(list(plan.entity_keys))
            if fact.get("chunk_uuid") and fact.get("subject") and fact.get("object") and fact.get("relation")
        ]

        if not candidates:
            return []

        evidence = {
            chunk["chunk_uuid"]: chunk
            for chunk in documents_chunk_collection.find(
                {
                    "$and": [
                        build_document_filter(ctx),
                        {"chunk_uuid": {"$in": list({f["chunk_uuid"] for f in candidates})}},
                    ]
                },
                {"_id": 0, "chunk_uuid": 1, "document_uuid": 1, "source": 1, "page": 1},
            )
        }

    except Exception as exc:
        logger.warning("Graph facts unavailable: %s: %s", type(exc).__name__, exc)
        return []

    facts = {}

    for fact in candidates:
        chunk = evidence.get(fact["chunk_uuid"])
        key = (fact["subject"], fact["relation"], fact["object"])

        if chunk is None or key in facts:
            continue

        facts[key] = {
            "subject": fact["subject"],
            "relation": fact["relation"],
            "object": fact["object"],
            "chunk_uuid": chunk["chunk_uuid"],
            "document_uuid": chunk.get("document_uuid"),
            "source": chunk.get("source", "Unknown document"),
            "page": chunk.get("page"),
        }

        if len(facts) >= MAX_GRAPH_FACTS:
            break

    return list(facts.values())


def _load_entity_chunks(chunk_uuids: list, ctx: UserContext, question_embedding: list) -> list:
    """
    Load entity-matched chunks from MongoDB WITH the permission filter,
    and score them like $vectorSearch does (cosine -> (1 + cos) / 2).
    """

    if not chunk_uuids:
        return []

    query = {
        "$and": [
            build_document_filter(ctx),
            {"chunk_uuid": {"$in": chunk_uuids}},
        ]
    }

    projection = {
        "_id": 0,
        "chunk_uuid": 1,
        "text": 1,
        "source": 1,
        "page": 1,
        "document_uuid": 1,
        "embedding": 1,
    }

    chunks = []

    for chunk in documents_chunk_collection.find(query, projection):
        # Embeddings are normalized, so the dot product is the cosine similarity.
        embedding = chunk.pop("embedding", None) or []
        cosine = sum(a * b for a, b in zip(question_embedding, embedding))
        chunk["score"] = (1 + cosine) / 2
        chunks.append(chunk)

    return chunks


def _select_chunks(
    candidates: list,
    limit: int,
    max_per_document: int,
    score_key: str = "score",
) -> list:
    """
    Remove duplicate chunks, prioritize higher scores (vector `score`
    by default, `rerank_score` after reranking), and limit how many
    chunks come from each document.
    """

    unique_chunks = {}

    for chunk in candidates:
        # Prefer the unique chunk ID. Use a fallback for older records.
        key = chunk.get("chunk_uuid") or (
            chunk.get("document_uuid"),
            chunk.get("page"),
            chunk.get("text"),
        )

        if key not in unique_chunks:
            unique_chunks[key] = chunk

    ranked_chunks = sorted(
        unique_chunks.values(),
        key=lambda chunk: chunk.get(score_key, 0),
        reverse=True,
    )

    selected_chunks = []
    chunks_per_document = defaultdict(int)

    for chunk in ranked_chunks:
        document_uuid = chunk.get("document_uuid")

        if chunks_per_document[document_uuid] >= max_per_document:
            continue

        selected_chunks.append(chunk)
        chunks_per_document[document_uuid] += 1

        if len(selected_chunks) >= limit:
            break

    return selected_chunks


def retrieve_relevant_chunks(
    question: str,
    ctx: UserContext,
    limit: int = 10,
    max_per_document: int = 3,
    plan: RetrievalPlan | None = None,
) -> list:
    """
    Retrieve accessible chunks using MongoDB vector search
    and Neo4j shared-topic and entity relationships.

    `plan` (from plan_retrieval) says whether the entity graph is needed; without
    one, entities are detected here. The entity graph runs even when vector
    search finds nothing, so a question naming a known entity can still be answered.

    MongoDB remains responsible for permission-filtered content.
    Neo4j only helps discover potentially related documents.

    With reranking on, a wider pool (RERANK_CANDIDATES) is scored by a
    cross-encoder and at most RERANK_TOP_N chunks are returned, each
    carrying `rerank_score`. If reranking is off or fails, the original
    vector-score selection (`limit` chunks) is used unchanged.
    """

    reranking_enabled = rerank_service.RERANK_PROVIDER != "none"

    try:
        question_embedding = get_embedding().embed_query(question)

        # 1. Find relevant, accessible chunks using Hybrid Search (Vector + Keyword)
        candidate_limit = rerank_service.RERANK_CANDIDATES if reranking_enabled else 30

        vector_chunks = _vector_search(
            question_embedding=question_embedding,
            ctx=ctx,
            candidate_limit=candidate_limit,
        )

        keyword_chunks = _keyword_search(
            question=question,
            ctx=ctx,
            candidate_limit=candidate_limit,
        )

        if keyword_chunks:
            initial_chunks = _reciprocal_rank_fusion(vector_chunks, keyword_chunks)
        else:
            initial_chunks = vector_chunks
        
        # 2. Discover documents connected through shared topics
        # (needs vector results as seeds).
        seed_document_uuids = list({
            chunk["document_uuid"]
            for chunk in initial_chunks
            if chunk.get("document_uuid")
        })

        try:
            related_document_uuids = (
                _find_related_document_uuids(seed_document_uuids)
                if seed_document_uuids
                else []
            )

            # 3. Search related documents in MongoDB.
            # The permission filter is applied again inside this query.
            if related_document_uuids:
                graph_chunks = _vector_search(
                    question_embedding=question_embedding,
                    ctx=ctx,
                    candidate_limit=30,
                    document_uuids=related_document_uuids,
                )
            else:
                graph_chunks = []

        except Exception as graph_exc:
            # Neo4j is an enhancement, not a requirement for basic RAG.
            logger.warning("Graph-assisted retrieval unavailable: %s: %s", type(graph_exc).__name__, graph_exc)
            graph_chunks = []

        # 3b. Entity graph: chunks mentioning entities named in the question.
        # Neo4j gives chunk IDs only; MongoDB applies the permission filter.
        try:
            if plan is None:
                entity_chunk_uuids = _find_entity_chunk_uuids(question)
            elif plan.use_entity_graph:
                with get_neo4j_driver().session(database=NEO4J_DATABASE) as session:
                    entity_chunk_uuids = _entity_chunk_uuids_for_keys(session, plan.entity_keys)
            else:
                entity_chunk_uuids = []

            entity_chunks = _load_entity_chunks(entity_chunk_uuids, ctx, question_embedding)

        except Exception as entity_exc:
            # The entity graph is an enhancement, not a requirement for basic RAG.
            logger.warning("Entity-graph retrieval unavailable: %s: %s", type(entity_exc).__name__, entity_exc)
            entity_chunks = []

        # 4. Combine vector, topic-graph and entity-graph candidates.
        # Duplicate chunks are removed and higher scores are prioritized.

        entity_chunks = sorted(entity_chunks, key=lambda c: c.get("score", 0), reverse=True)
        all_candidates = _fuse_ranked_lists(vector_chunks, keyword_chunks, graph_chunks, entity_chunks)

        if not all_candidates:
            return []

        # 5. Rerank: score the best RERANK_CANDIDATES (deduplicated) with a
        # cross-encoder and keep the top RERANK_TOP_N for the LLM.
        if reranking_enabled:
            pool = _select_chunks(
                candidates=all_candidates,
                limit=rerank_service.RERANK_CANDIDATES,
                max_per_document=rerank_service.RERANK_CANDIDATES,
            )
            reranked = rerank_service.rerank(question, pool)

            if reranked is not None:
                return _select_chunks(
                    candidates=reranked,
                    limit=min(limit, rerank_service.RERANK_TOP_N),
                    max_per_document=max_per_document,
                    score_key="rerank_score",
                )

        # Reranking off or unavailable: original vector-score selection.
        return _select_chunks(
            candidates=all_candidates,
            limit=limit,
            max_per_document=max_per_document,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Document retrieval error")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve relevant document chunks.",
        ) from exc
