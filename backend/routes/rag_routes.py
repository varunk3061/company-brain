import re

from fastapi import APIRouter, Depends, HTTPException

from models.rag_model import AskQuestionRequest
from services import audit_service
from services import chat_service
from services import rerank_service
from services.access.policy import UserContext
from services.llm_service import generate_answer, is_abstention
from services.retrieval_service import plan_retrieval, retrieve_graph_facts, retrieve_relevant_chunks
from services.intent_service import detect_intent
from utils.auth import get_current_user

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/api/rag", tags=["Company Brain RAG"])

NO_ANSWER = "I could not find this information in the accessible documents."

# Follow-up fallback: how many earlier questions of the same conversation are added to a weak follow-up.
HISTORY_QUESTIONS = 2


def _retrieve(search_text: str, ctx: UserContext):
    """One retrieval pass (unchanged logic): plan, permission-filtered chunks, graph facts."""

    plan = plan_retrieval(search_text)

    # At most 3 chunks per document, so multi-document questions (impact, dependencies) get a wider mix of sources.
    chunks = retrieve_relevant_chunks(question=search_text, ctx=ctx, limit=10, max_per_document=3, plan=plan)
    facts = retrieve_graph_facts(plan, ctx)
    return plan, chunks, facts


def _name_key(text) -> str:
    """Lowercase, letters/digits only, padded with spaces so file names match as whole words."""
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip() + " "


def _cited_in_answer(sources: list, answer: str) -> list:
    """Keep only the sources whose document name appears in the answer.

    If the answer names none of them (the model cited nothing explicitly), every source is kept,
    so a real answer never loses all of its citations.
    """

    answer_key = _name_key(answer)
    cited = []

    for s in sources:
        name = str(s.get("source") or "")
        stem = name[:-4] if name.lower().endswith(".pdf") else name
        if _name_key(stem).strip() and _name_key(stem) in answer_key:
            cited.append(s)

    return cited or sources


def _is_weak(chunks: list, facts: list) -> bool:
    """True when this pass would end in a refusal: nothing found, or only low-relevance chunks."""

    if not chunks and not facts:
        return True
    return not facts and rerank_service.is_low_confidence(chunks)


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

    #-------------------------------------------------------
    # Intent detection: Handle greetings without RAG
    #-------------------------------------------------------
    intent, direct_response = detect_intent(question)

    if intent == "greeting":
        conv_id, num = chat_service.save_chat_turn(
            user_uuid=ctx.user_uuid,
            conversation_id=request.conversation_id,
            question=question,
            answer=direct_response,
            sources=[]
        )

        return {
            "answer": direct_response,
            "sources": [],
            "conversation_id": conv_id,
            "num": num
        }
    
    #-------------------------------------------------------
    # Existing RAG pipeline
    #-------------------------------------------------------
    plan, chunks, facts = _retrieve(question, ctx)

    # Follow-up fallback: a short follow-up ("how many days carry over?") has no topic of its own.
    # Only when the question alone would be refused, retry once with the conversation's last
    # questions in front of it. Standalone questions never reach this, so they behave as before.
    # Permissions are unchanged: the retry goes through the same filtered retrieval.
    llm_question = question
    history = []

    if request.conversation_id is not None and _is_weak(chunks, facts):
        history = chat_service.get_recent_user_questions(
            request.conversation_id, ctx.user_uuid, limit=HISTORY_QUESTIONS
        )

        if history:
            retry = _retrieve(" ".join(history + [question]), ctx)

            if not _is_weak(retry[1], retry[2]):
                plan, chunks, facts = retry
                llm_question = (
                    "Earlier questions in this conversation (context only):\n"
                    + "\n".join(f"- {q}" for q in history)
                    + f"\n\nCurrent question: {question}"
                )
            else:
                history = []

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

    answer = generate_answer(question=llm_question, context=context)
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

    # Show only the documents the answer actually cites, not every retrieved chunk.
    sources = _cited_in_answer(sources, answer)

    audit_after = {
        "question": question,
        "chunks": len(chunks),
        "route": plan.name,
        "graph_facts": len(facts),
        "documents": sorted({s["document_uuid"] for s in sources if s["document_uuid"]}),
    }
    if history:
        audit_after["history_questions"] = len(history)
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
