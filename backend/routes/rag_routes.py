from fastapi import APIRouter, Depends, HTTPException

from models.rag_model import AskQuestionRequest
from services import audit_service
from services import chat_service
from services import rerank_service
from services.access.policy import UserContext
from services.llm_service import generate_answer, is_abstention
from services.retrieval_service import plan_retrieval, retrieve_graph_facts, retrieve_relevant_chunks
from utils.auth import get_current_user

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/api/rag", tags=["Company Brain RAG"])

NO_ANSWER = "I could not find this information in the accessible documents."


def _no_answer(ctx: UserContext, request: AskQuestionRequest, question: str, audit_after: dict) -> dict:
    """Refuse without calling the LLM, but keep the turn in chat history like any other answer."""

    audit_service.record(ctx, "rag.ask", question, after=audit_after)

    # Saved so a new chat gets a real conversation_id; otherwise the next question in that
    # chat would be sent with the browser's temporary id and fail.
    conv_id, num = chat_service.save_chat_turn(
        user_uuid=ctx.user_uuid,
        conversation_id=request.conversation_id,
        question=question,
        answer=NO_ANSWER,
        sources=[],
    )
    return {"answer": NO_ANSWER, "sources": [], "conversation_id": conv_id, "num": num}


@router.post("/ask")
def ask_question(request: AskQuestionRequest, ctx: UserContext = Depends(get_current_user)):
    """Answer from documents the caller may see. Permissions are applied inside the retrieval query."""

    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    # Checked up front so a foreign or unknown conversation costs no retrieval or LLM call.
    if request.conversation_id is not None and not chat_service.conversation_belongs_to(
        request.conversation_id, ctx.user_uuid
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Router: entities named in the question decide whether the graph paths run.
    plan = plan_retrieval(question)

    # At most 3 chunks per document, so multi-document questions (impact, dependencies) get a wider mix of sources.
    chunks = retrieve_relevant_chunks(question=question, ctx=ctx, limit=10, max_per_document=3, plan=plan)
    facts = retrieve_graph_facts(plan, ctx)

    # Same text for "nothing exists" and "nothing you may see": a refusal must not reveal which it is.
    if not chunks and not facts:
        return _no_answer(ctx, request, question, {"question": question, "chunks": 0, "route": plan.name})

    rerank_details = rerank_service.audit_summary(chunks)

    # The reranker judged even the best permitted chunk irrelevant (and the graph had no
    # relation for the named entities): abstain with the same text.
    if not facts and rerank_service.is_low_confidence(chunks):
        return _no_answer(ctx, request, question, {
            "question": question,
            "chunks": len(chunks),
            "route": plan.name,
            "abstained": "low_rerank_score",
            "rerank": rerank_details,
        })

    context_parts = [
        f"Source: {chunk.get('source', 'Unknown document')}\n"
        f"Page: {chunk.get('page')}\n"
        f"Content:\n{chunk.get('text', '')}"
        for chunk in chunks
    ]

    if facts:
        context_parts.append(
            "Knowledge-graph facts (each extracted from the cited document page):\n"
            + "\n".join(
                f"- {f['subject']} {f['relation']} {f['object']} "
                f"(Source: {f['source']}, Page: {f['page']})"
                for f in facts
            )
        )

    context = "\n\n---\n\n".join(context_parts)

    answer = generate_answer(question=question, context=context)
    abstained = is_abstention(answer)

    # One entry per (document, page) actually retrieved: chunks first, then fact evidence.
    # An answer that declines to answer cites nothing: the documents did not support it.
    sources = [] if abstained else list({
        (c.get("document_uuid"), c.get("page")): {
            "source": c.get("source", "Unknown document"),
            "page": c.get("page"),
            "document_uuid": c.get("document_uuid"),
        }
        for c in chunks + facts
    }.values())

    audit_after = {
        "question": question,
        "chunks": len(chunks),
        "route": plan.name,
        "graph_facts": len(facts),
        "documents": sorted({s["document_uuid"] for s in sources if s["document_uuid"]}),
    }
    if abstained:
        audit_after["abstained"] = "llm"
    if rerank_details:
        audit_after["rerank"] = rerank_details

    audit_service.record(ctx, "rag.ask", question, after=audit_after)

    conv_id, num = chat_service.save_chat_turn(
        user_uuid=ctx.user_uuid,
        conversation_id=request.conversation_id,
        question=question,
        answer=answer,
        sources=sources
    )
    return {
        "answer": answer,
        "sources": sources,
        "conversation_id": conv_id,
        "num": num
    }
