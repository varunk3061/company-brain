"""Company Brain MCP server configuration."""
from MCP.auth import CompanyBrainTokenVerifier
from mcp.server.fastmcp import FastMCP
from MCP.tool import register_tools
from mcp.server.auth.settings import AuthSettings

mcp = FastMCP(
    name="Company Brain",
    instructions=(
        "Use the available tools to answer questions only from the "
        "authenticated user's permitted Company Brain documents. "
        "Always return citations when evidence is available."
    ),
    auth=AuthSettings(
        issuer_url="http://127.0.0.1:8000",
        resource_server_url="http://127.0.0.1:8000/mcp",
        required_scopes=["company_brain.ask"],
    ),
    token_verifier=CompanyBrainTokenVerifier(),
    streamable_http_path="/",
    json_response=True,
)

register_tools(mcp)


def create_mcp_app():
    """Return the ASGI application that FastAPI will mount at /mcp."""

    return mcp.streamable_http_app()