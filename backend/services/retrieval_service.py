# from fastapi import HTTPException

# from collections import defaultdict
# from database.connection import documents_chunk_collection
# from database.neo4j_connection import (get_neo4j_driver, NEO4J_DATABASE)
# from services.access.policy import (UserContext, build_document_filter)
# from services.embedding_service import get_embedding

# #-------------------------------------------------------------------------------------

# # IMPORTANT: This must exactly match your MongoDB Atlas index name.
# VECTOR_INDEX_NAME = "vector_index"

# #-------------------------------------------------------------------------------------

# def retrieve_relevant_chunks(question: str, ctx: UserContext, limit: int = 10, max_per_document: int = 4,) -> list:
#     """Top chunks for `question` that `ctx` is allowed to see.

#     The permission filter is applied INSIDE the vector query (pre-filter), never after top-k,
#     so restricted text never leaves the database for this user.
#     """

#     try:
#         question_embedding = get_embedding().embed_query(question)

#         # Retrieve more candidates than we ultimately need.
#         candidate_limit = 30

#         pipeline = [
#             {
#                 "$vectorSearch": {
#                     "index": VECTOR_INDEX_NAME,
#                     "path": "embedding",
#                     "queryVector": question_embedding,
#                     "numCandidates": 100,
#                     "limit": candidate_limit,

#                      # Permissions are applied inside vector search.
#                     "filter": build_document_filter(ctx),
#                 }
#             },
#             {
#                 "$project": {
#                     "_id": 0,
#                     "text": 1,
#                     "source": 1,
#                     "page": 1,
#                     "document_uuid": 1,
#                     "score": {"$meta": "vectorSearchScore"},
#                 }
#             },
#         ]

#         candidates = list (
#             documents_chunk_collection.aggregate(pipeline)
#         )

#         # Prefer relevant chunks from different documents,
#         # while keeping the original relevance order.
#         selected_chunks = []
#         chunks_per_document = defaultdict(int)

#         for chunk in candidates:
#             document_uuid = chunk.get("document_uuid")

#             if chunks_per_document[document_uuid] >= max_per_document:
#                 continue

#             selected_chunks.append(chunk)
#             chunks_per_document[document_uuid] += 1

#             if len(selected_chunks) >= limit:
#                 break

#         return selected_chunks

#         # return list(documents_chunk_collection.aggregate(pipeline))

#     except HTTPException:
#         raise

#     except Exception as exc:
#         print(
#             f"Document retrieval error: "
#             f"{type(exc).__name__}: {exc}"
#         )

#         raise HTTPException(
#             status_code=500,
#             detail="Could not retrieve relevant document chunks.",
#         ) from exc



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

        # 4. Combine vector and graph-assisted candidates.
        # Duplicate chunks are removed and higher scores are prioritized.
        all_candidates = initial_chunks + graph_chunks

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
