from typing import Optional
from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id : Optional[str] = None
