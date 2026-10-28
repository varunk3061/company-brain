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
from services.embedding_service import get_embedding


# Must exactly match the Atlas Vector Search index name.
VECTOR_INDEX_NAME = "vector_index"

# Maximum number of additional documents discovered through Neo4j.
MAX_GRAPH_DOCUMENTS = 10

# Maximum number of chunks found through entity matching.
MAX_ENTITY_CHUNKS = 15


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


def _find_entity_chunk_uuids(question: str) -> list:
    """
    Ask Neo4j for chunks that mention entities named in the question,
    or entities directly related to them.

    Only chunk IDs are returned. Content is loaded from MongoDB
    with the user's permission filter.
    """

    driver = get_neo4j_driver()
    question_text = _normalize_text(question)

    with driver.session(database=NEO4J_DATABASE) as session:
        # 1. Entities whose name appears in the question as whole words.
        #    Keys shorter than 3 characters are skipped (too many false matches).
        keys = [
            record["key"]
            for record in session.run("MATCH (e:Entity) RETURN e.key AS key")
            if record["key"]
            and len(record["key"]) >= 3
            and _normalize_text(record["key"]) in question_text
        ]

        if not keys:
            return []

        # 2. Chunks mentioning those entities or their direct neighbours.
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
            keys=keys,
            max_chunks=MAX_ENTITY_CHUNKS,
        )

        return [record["chunk_uuid"] for record in records if record["chunk_uuid"]]


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
) -> list:
    """
    Remove duplicate chunks, prioritize higher vector scores,
    and limit how many chunks come from each document.
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
        key=lambda chunk: chunk.get("score", 0),
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
    max_per_document: int = 4,
) -> list:
    """
    Retrieve accessible chunks using MongoDB vector search
    and Neo4j shared-topic relationships.

    MongoDB remains responsible for permission-filtered content.
    Neo4j only helps discover potentially related documents.
    """

    try:
        question_embedding = get_embedding().embed_query(question)

        # 1. Find relevant, accessible chunks in MongoDB.
        initial_chunks = _vector_search(
            question_embedding=question_embedding,
            ctx=ctx,
            candidate_limit=30,
        )

        if not initial_chunks:
            return []

        # 2. Discover documents connected through shared topics.
        seed_document_uuids = list({
            chunk["document_uuid"]
            for chunk in initial_chunks
            if chunk.get("document_uuid")
        })

        try:
            related_document_uuids = (
                _find_related_document_uuids(seed_document_uuids)
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
            print(
                "Graph-assisted retrieval unavailable: "
                f"{type(graph_exc).__name__}: {graph_exc}"
            )
            graph_chunks = []

        # 3b. Entity graph: chunks mentioning entities named in the question.
        # Neo4j gives chunk IDs only; MongoDB applies the permission filter.
        try:
            entity_chunk_uuids = _find_entity_chunk_uuids(question)
            entity_chunks = _load_entity_chunks(entity_chunk_uuids, ctx, question_embedding)

        except Exception as entity_exc:
            # The entity graph is an enhancement, not a requirement for basic RAG.
            print(
                "Entity-graph retrieval unavailable: "
                f"{type(entity_exc).__name__}: {entity_exc}"
            )
            entity_chunks = []

        # 4. Combine vector, topic-graph and entity-graph candidates.
        # Duplicate chunks are removed and higher scores are prioritized.
        all_candidates = initial_chunks + graph_chunks + entity_chunks

        return _select_chunks(
            candidates=all_candidates,
            limit=limit,
            max_per_document=max_per_document,
        )

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "Document retrieval error: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve relevant document chunks.",
        ) from exc
