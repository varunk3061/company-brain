from fastapi import APIRouter, Depends, HTTPException

from models.rag_model import AskQuestionRequest
from services import audit_service
from services.access.policy import UserContext
from services.llm_service import generate_answer
from services.retrieval_service import retrieve_relevant_chunks
from utils.auth import get_current_user

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/api/rag", tags=["Company Brain RAG"])

NO_ANSWER = "I could not find this information in the accessible documents."


@router.post("/ask")
def ask_question(request: AskQuestionRequest, ctx: UserContext = Depends(get_current_user)):
    """Answer from documents the caller may see. Permissions are applied inside the retrieval query."""

    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    chunks = retrieve_relevant_chunks(question=question, ctx=ctx, limit=10,max_per_document=4)

    # Same text for "nothing exists" and "nothing you may see": a refusal must not reveal which it is.
    if not chunks:
        audit_service.record(ctx, "rag.ask", "query", after={"question": question, "chunks": 0})
        return {"answer": NO_ANSWER, "sources": []}

    context = "\n\n---\n\n".join(
        f"Source: {chunk.get('source', 'Unknown document')}\n"
        f"Page: {chunk.get('page')}\n"
        f"Content:\n{chunk.get('text', '')}"
        for chunk in chunks
    )

    answer = generate_answer(question=question, context=context)

    # One entry per (document, page) actually retrieved.
    sources = list({
        (c.get("document_uuid"), c.get("page")): {
            "source": c.get("source", "Unknown document"),
            "page": c.get("page"),
            "document_uuid": c.get("document_uuid"),
        }
        for c in chunks
    }.values())

    audit_service.record(
        ctx, "rag.ask", "query",
        after={"question": question, "chunks": len(chunks), "documents": sorted({s["document_uuid"] for s in sources})},
    )

    return {"answer": answer, "sources": sources}
