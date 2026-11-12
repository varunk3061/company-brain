from fastapi import APIRouter, Depends, HTTPException

from models.rag_model import AskQuestionRequest
from services.access.policy import UserContext
from services.company_brain_service import answer_question
from utils.auth import get_current_user

router = APIRouter(prefix="/api/rag", tags=["Company Brain RAG"])


@router.post("/ask")
def ask_question(
    request: AskQuestionRequest,
    ctx: UserContext = Depends(get_current_user),
):
    """Answer from documents the authenticated user may access."""

    try:
        return answer_question(
            ctx=ctx,
            question=request.question,
            conversation_id=request.conversation_id,
            use_conversation_history=True,
            persist_chat=True,
            audit_action="rag.ask",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc