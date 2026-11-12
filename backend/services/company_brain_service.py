"""Shared, permission-aware Company Brain question-answering workflow."""

import re
from typing import Any

from fastapi import HTTPException

from services import audit_service, chat_service, rerank_service
from services.access.policy import UserContext
from services.intent_service import detect_intent
from services.llm_service import generate_answer, is_abstention
from services.retrieval_service import (
    plan_retrieval,
    retrieve_graph_facts,
    retrieve_relevant_chunks,
)

NO_ANSWER = "I could not find this information in the accessible documents."
HISTORY_QUESTIONS = 2


def _retrieve(search_text: str, ctx: UserContext) -> tuple[Any, list, list]:
    """Retrieve only evidence visible to the authenticated user."""

    plan = plan_retrieval(search_text)

    chunks = retrieve_relevant_chunks(
        question=search_text,
        ctx=ctx,
        limit=10,
        max_per_document=3,
        plan=plan,
    )
    facts = retrieve_graph_facts(plan, ctx)

    return plan, chunks, facts


def _name_key(text: str | None) -> str:
    """Normalize a filename for safe citation matching."""

    return " " + re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip() + " "


def _cited_in_answer(sources: list[dict], answer: str) -> list[dict]:
    """Return sources named by the answer, or all retrieved sources as fallback."""

    answer_key = _name_key(answer)
    cited = []

    for source in sources:
        name = str(source.get("source") or "")
        stem = name[:-4] if name.lower().endswith(".pdf") else name

        if _name_key(stem).strip() and _name_key(stem) in answer_key:
            cited.append(source)

    return cited or sources


def _is_weak(chunks: list, facts: list) -> bool:
    """Return true when permitted evidence cannot support an answer."""

    if not chunks and not facts:
        return True

    return not facts and rerank_service.is_low_confidence(chunks)


def _save_chat_turn_if_needed(
    *,
    persist_chat: bool,
    user_uuid: str,
    conversation_id: str | None,
    question: str,
    answer: str,
    sources: list[dict],
) -> tuple[str | None, int | None]:
    """Save a website-chat turn only when the caller requested persistence."""

    if not persist_chat:
        return None, None

    return chat_service.save_chat_turn(
        user_uuid=user_uuid,
        conversation_id=conversation_id,
        question=question,
        answer=answer,
        sources=sources,
    )


def _no_answer(
    *,
    ctx: UserContext,
    question: str,
    audit_action: str,
    audit_after: dict,
    conversation_id: str | None,
    persist_chat: bool,
) -> dict:
    """Return the same refusal for missing, inaccessible, or weak evidence."""

    audit_service.record(ctx, audit_action, question, after=audit_after)

    saved_conversation_id, num = _save_chat_turn_if_needed(
        persist_chat=persist_chat,
        user_uuid=ctx.user_uuid,
        conversation_id=conversation_id,
        question=question,
        answer=NO_ANSWER,
        sources=[],
    )

    return {
        "answer": NO_ANSWER,
        "sources": [],
        "conversation_id": saved_conversation_id,
        "num": num,
    }


def answer_question(
    *,
    ctx: UserContext,
    question: str,
    conversation_id: str | None = None,
    use_conversation_history: bool = False,
    persist_chat: bool = False,
    audit_action: str = "rag.ask",
) -> dict:
    """Answer only from evidence the current user is allowed to access."""

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    # Only website chat currently uses Company Brain conversation history.
    if conversation_id is not None and persist_chat:
        if not chat_service.conversation_belongs_to(conversation_id, ctx.user_uuid):
            raise HTTPException(status_code=404, detail="Conversation not found")

    intent, direct_response = detect_intent(cleaned_question)

    if intent == "greeting":
        audit_service.record(
            ctx,
            audit_action,
            cleaned_question,
            after={
                "question": cleaned_question,
                "route": "greeting",
                "chunks": 0,
            },
        )

        saved_conversation_id, num = _save_chat_turn_if_needed(
            persist_chat=persist_chat,
            user_uuid=ctx.user_uuid,
            conversation_id=conversation_id,
            question=cleaned_question,
            answer=direct_response,
            sources=[],
        )

        return {
            "answer": direct_response,
            "sources": [],
            "conversation_id": saved_conversation_id,
            "num": num,
        }

    plan, chunks, facts = _retrieve(cleaned_question, ctx)

    llm_question = cleaned_question
    history: list[str] = []

    # MCP should initially pass False here. Website chat passes True.
    if use_conversation_history and conversation_id is not None and _is_weak(chunks, facts):
        history = chat_service.get_recent_user_questions(
            conversation_id,
            ctx.user_uuid,
            limit=HISTORY_QUESTIONS,
        )

        if history:
            retry_plan, retry_chunks, retry_facts = _retrieve(
                " ".join(history + [cleaned_question]),
                ctx,
            )

            if not _is_weak(retry_chunks, retry_facts):
                plan = retry_plan
                chunks = retry_chunks
                facts = retry_facts
                llm_question = (
                    "Earlier questions in this conversation (context only):\n"
                    + "\n".join(f"- {item}" for item in history)
                    + f"\n\nCurrent question: {cleaned_question}"
                )
            else:
                history = []

    if not chunks and not facts:
        return _no_answer(
            ctx=ctx,
            question=cleaned_question,
            audit_action=audit_action,
            audit_after={
                "question": cleaned_question,
                "chunks": 0,
                "route": plan.name,
            },
            conversation_id=conversation_id,
            persist_chat=persist_chat,
        )

    rerank_details = rerank_service.audit_summary(chunks)

    if not facts and rerank_service.is_low_confidence(chunks):
        return _no_answer(
            ctx=ctx,
            question=cleaned_question,
            audit_action=audit_action,
            audit_after={
                "question": cleaned_question,
                "chunks": len(chunks),
                "route": plan.name,
                "abstained": "low_rerank_score",
                "rerank": rerank_details,
            },
            conversation_id=conversation_id,
            persist_chat=persist_chat,
        )

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
                f"- {fact['subject']} {fact['relation']} {fact['object']} "
                f"(Source: {fact['source']}, Page: {fact['page']})"
                for fact in facts
            )
        )

    answer = generate_answer(
        question=llm_question,
        context="\n\n---\n\n".join(context_parts),
    )
    abstained = is_abstention(answer)

    sources = [] if abstained else list({
        (item.get("document_uuid"), item.get("page")): {
            "source": item.get("source", "Unknown document"),
            "page": item.get("page"),
            "document_uuid": item.get("document_uuid"),
        }
        for item in chunks + facts
    }.values())

    sources = _cited_in_answer(sources, answer)

    audit_after = {
        "question": cleaned_question,
        "chunks": len(chunks),
        "route": plan.name,
        "graph_facts": len(facts),
        "documents": sorted({
            source["document_uuid"]
            for source in sources
            if source["document_uuid"]
        }),
    }

    if history:
        audit_after["history_questions"] = len(history)

    if abstained:
        audit_after["abstained"] = "llm"

    if rerank_details:
        audit_after["rerank"] = rerank_details

    audit_service.record(ctx, audit_action, cleaned_question, after=audit_after)

    saved_conversation_id, num = _save_chat_turn_if_needed(
        persist_chat=persist_chat,
        user_uuid=ctx.user_uuid,
        conversation_id=conversation_id,
        question=cleaned_question,
        answer=answer,
        sources=sources,
    )

    return {
        "answer": answer,
        "sources": sources,
        "conversation_id": saved_conversation_id,
        "num": num,
    }