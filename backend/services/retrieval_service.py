from fastapi import HTTPException

from database.connection import documents_chunk_collection
from services.access.policy import UserContext, build_document_filter
from services.embedding_service import get_embedding

#-------------------------------------------------------------------------------------

VECTOR_INDEX_NAME = "vector_index"


def retrieve_relevant_chunks(question: str, ctx: UserContext, limit: int = 5) -> list:
    """Top chunks for `question` that `ctx` is allowed to see.

    The permission filter is applied INSIDE the vector query (pre-filter), never after top-k,
    so restricted text never leaves the database for this user.
    """

    try:
        question_embedding = get_embedding().embed_query(question)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": question_embedding,
                    "numCandidates": 100,
                    "limit": limit,
                    "filter": build_document_filter(ctx),
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "text": 1,
                    "source": 1,
                    "page": 1,
                    "document_uuid": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        return list(documents_chunk_collection.aggregate(pipeline))

    except HTTPException:
        raise
    except Exception as exc:
        print(f"Document retrieval error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve relevant document chunks.",
        ) from exc
