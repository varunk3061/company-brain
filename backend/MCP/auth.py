"""JWT verification for Company Brain MCP requests."""

from fastapi import HTTPException
from mcp.server.auth.provider import AccessToken

from database.connection import users_collection
from utils.auth import build_user_context, verify_access_token


class CompanyBrainTokenVerifier:
    """Verify the existing Company Brain JWT on every MCP request."""

    async def verify_token(self, token: str) -> AccessToken | None:
        payload = verify_access_token(token)
        user_uuid = (payload or {}).get("sub")

        if not user_uuid:
            return None

        user = users_collection.find_one({"user_uuid": user_uuid})

        if not user or user.get("status") != "active":
            return None

        try:
            # Confirms the role remains active and loads current permissions.
            build_user_context(user)
        except HTTPException:
            return None

        return AccessToken(
            token=token,
            # tool.py uses this verified ID to load a fresh UserContext.
            client_id=user_uuid,
            scopes=["company_brain.ask"],
        )