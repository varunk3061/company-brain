from fastapi import APIRouter, Depends, HTTPException
from services.access.policy import UserContext
from services import chat_service
from utils.auth import get_current_user

#---------------------------------------------------------------------------------------------------

router = APIRouter(prefix="/api/chat", tags=["Chat History"])

#---------------------------------------------------------------------------------------------------

@router.get("/conversations")
def list_convesations(ctx: UserContext = Depends(get_current_user)):

    """List conversations belonging to the authenticated user. """

    return chat_service.get_user_conversations(ctx.user_uuid)

#---------------------------------------------------------------------------------------------------

@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id:str, ctx: UserContext = Depends(get_current_user)):

     """Retrieve messages from a conversation owned by the user."""

     conversation = chat_service.get_conversation_by_uuid(
          conversation_id = conversation_id,
          user_uuid=ctx.user_uuid
     )

     if conversation is None:
          raise HTTPException(
               status_code=404, 
               detail="Conversation not found",
          )

     return conversation

#---------------------------------------------------------------------------------------------------

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id:str, ctx:UserContext = Depends(get_current_user)):

    """Delete a conversation owned by the authenticated user."""

    success = chat_service.delete_conversation(
         conversation_id=conversation_id,
         user_uuid=ctx.user_uuid
    )

    if not success:
         raise HTTPException(
              status_code=404,
              detail="Conversation not found"
         )

    return {"message": "Conversation deleted successfully"}