from uuid import uuid4
from datetime import datetime, timezone
from database.connection import chat_conversations_collection

#---------------------------------------------------------------------------------------------------

def get_user_conversations(user_uuid:str):

    """Get conversation summaries from one user, newest first"""

    cursor = chat_conversations_collection.find(
        {"user_uuid":user_uuid},
        {
            "_id":0,
            "conversation_id":1,
            "title":1,
            "created_at":1,
            "updated_at":1,
            "num":1
        },
    ).sort("updated_at", -1)

    conversations = []

    for doc in cursor:
        updated_at = doc.get("updated_at")

        conversations.append(
            {
                "id": doc["conversation_id"],
                "_id": doc["conversation_id"],
                "title": doc.get("title", "New Conversation"),
                "num": doc.get("num", 1),
                "created_at": (
                    doc["created_at"].isoformat()
                    if isinstance(doc.get("created_at"),datetime)
                    else doc.get("created_at")
                ),
                "updated_at": (
                    updated_at.isoformat()
                    if isinstance(updated_at, datetime)
                    else updated_at
                ),
            }
        )
    return conversations

#---------------------------------------------------------------------------------------------------

def get_conversation_by_uuid(conversation_id: str, user_uuid: str):

    """Get a conversation only if it belongs to the authenticated user."""

    doc = chat_conversations_collection.find_one(
        {
            "conversation_id" : conversation_id,
            "user_uuid" : user_uuid
        },
        {"_id":0},
    )

    if not doc:
        return None

    raw_messages = doc.get("messages") or doc.get("message") or []
    messages = []
    for msg in raw_messages:
        if isinstance(msg, dict):
            msg_copy = dict(msg)
            if "sources" in msg_copy and isinstance(msg_copy["sources"], list):
                normalized_sources = []
                for s in msg_copy["sources"]:
                    if isinstance(s, dict):
                        doc_name = s.get("file") or s.get("source") or s.get("fileName") or "Unknown document"
                        normalized_sources.append({
                            **s,
                            "file": doc_name,
                            "source": doc_name,
                        })
                    else:
                        normalized_sources.append(s)
                msg_copy["sources"] = normalized_sources
            messages.append(msg_copy)
        else:
            messages.append(msg)
    return {
        "id": doc["conversation_id"],
        "_id": doc["conversation_id"],
        "conversation_id": doc["conversation_id"],
        "title": doc.get("title", "New Conversation"),
        "num": doc.get("num", 1),
        "created_at": (
            doc["created_at"].isoformat()
            if isinstance(doc.get("created_at"), datetime)
            else doc.get("created_at")
        ),
        "updated_at": (
            doc["updated_at"].isoformat()
            if isinstance(doc.get("updated_at"), datetime)
            else doc.get("updated_at")
        ),
        "messages": messages,
        "message": messages,
    }

#---------------------------------------------------------------------------------------------------

def save_chat_turn(
        user_uuid:str, conversation_id:str | None,
        question:str, answer:str, sources: list
        ):

    """
    Save a user question and assistant answer.

    Create a conversation if conversation_id is None.
    Otherwise, append both messages to existing conversation.
    Return (conversation_id, num).    
    """

    now = datetime.now(timezone.utc)

    # Create unique message IDs using full UUIDs.

    # 1. Structure the message objects
    user_msg = {
        "id" : str(uuid4()),
        "role" : "user",
        "text" : question,
        "created_at" : now.isoformat(),
    }

    paragraphs = [
        paragraph.strip()
        for paragraph in (answer or "").splitlines()
        if paragraph.strip()
    ]

    assistant_msg = {
        "id" : str(uuid4()),
        "role" : "assistant",
        "paragraphs" : paragraphs or ["No answer was returned."],
        "sources" : [
            {
                **s,
                "file": s.get("file") or s.get("source", "Unknown document"),
                "source": s.get("source") or s.get("file", "Unknown document"),
                }
                for s in (sources or [])
                ],
        "created_at" : now.isoformat(),
    }

    # Existing Conversation : verify ownership and append messages.

    # 2. Existing conversation: append messages
    if conversation_id is not None:
        existing = chat_conversations_collection.find_one(
            {
                "conversation_id" : conversation_id,
                "user_uuid" : user_uuid,
            },
            {"_id":0, "num":1},
        )

        if existing is None:
            raise ValueError(
                "Conversation not found or does not belong to this user."
            )

        chat_conversations_collection.update_one(
            {
                "conversation_id": conversation_id,
                "user_uuid": user_uuid,
            },
            {
                "$push": {
                    "messages": {
                        "$each": [user_msg, assistant_msg]
                    }
                },
                "$set": {"updated_at": now},
            },
        )

        return conversation_id, existing.get("num", 1) 

    # New conversation: create a UUID-based identifier.
    
    # 3. New conversation: create document
    new_conversation_id = str(uuid4())

    total_conversations = chat_conversations_collection.count_documents(
        {"user_uuid" : user_uuid}
    )

    num = total_conversations + 1

    title = question.strip()[:40]
    if len(question.strip()) > 40:
        title += "..."

    chat_conversations_collection.insert_one({
        "conversation_id": new_conversation_id,
        "messages" : [user_msg, assistant_msg],
        "user_uuid": user_uuid,
        "title": title or "New Conversation",
        "num": num,
        "created_at": now,
        "updated_at": now,
    })

    return new_conversation_id, num

#---------------------------------------------------------------------------------------------------

def delete_conversation(conversation_id: str, user_uuid: str):

    """Delete a conversation only if it belong to the authenticated user."""

    result = chat_conversations_collection.delete_one({
        "conversation_id" : conversation_id,
        "user_uuid" : user_uuid,
    })

    return result.deleted_count > 0

#---------------------------------------------------------------------------------------------------