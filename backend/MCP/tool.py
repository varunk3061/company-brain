"""Read-only MCP tools for Company Brain."""

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from database.connection import users_collection
from services.company_brain_service import answer_question
from utils.auth import build_user_context


def _get_authenticated_user_context():
    """Load the current active Company Brain user from the verified MCP token."""

    access_token = get_access_token()

    if access_token is None:
        raise PermissionError("Authentication is required.")

    # The MCP JWT verifier must set client_id to the verified JWT user's UUID.
    user_uuid = access_token.client_id

    user = users_collection.find_one({"user_uuid": user_uuid})

    if not user or user.get("status") != "active":
        raise PermissionError("Authentication is required.")

    return build_user_context(user)


def register_tools(mcp: FastMCP) -> None:
    """Register Company Brain's read-only MCP tools."""

    @mcp.tool(
        name="ask_company_brain",
        description=(
            "Answer a Company Brain question using only documents that the "
            "authenticated employee is currently permitted to access. "
            "Returns citations when evidence supports the answer."
        ),
    )
    def ask_company_brain(question: str) -> dict:
        """Answer a question from permitted Company Brain evidence only."""

        ctx = _get_authenticated_user_context()

        result = answer_question(
            ctx=ctx,
            question=question,
            use_conversation_history=False,
            persist_chat=False,
            audit_action="mcp.ask",
        )

        return {
            "answer": result["answer"],
            "sources": result["sources"],
        }