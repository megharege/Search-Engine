import os
from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
from search_core import hybrid_search, fetch_chunk_by_id, get_available_texts, get_available_categories

# Create FastMCP instance
mcp = FastMCP("ayurveda-rag")

@mcp.tool()
def search_verses(query: str, sthana: str | None = None, primary_category: str | None = None, limit: int = 10) -> list[dict]:
    """Hybrid keyword + semantic search over classical Ayurvedic texts.
    Returns matching chunks with chunk_id, sthana, verse_id, sanskrit_text,
    transliteration, topic_heading, commentary, and relevance score."""
    return hybrid_search(query=query, sthana=sthana, primary_category=primary_category, limit=limit)

@mcp.tool()
def get_chunk(chunk_id: str) -> dict:
    """Fetch the full record for a single chunk by its chunk_id."""
    return fetch_chunk_by_id(chunk_id)

@mcp.tool()
def list_texts() -> list[str]:
    """List all source book titles / sthanas available in the index."""
    return get_available_texts()

@mcp.tool()
def list_categories() -> list[str]:
    """List all distinct primary_category values available in the index."""
    return get_available_categories()

# Simple ASGI wrapper for authentication
class AuthMiddleware:
    def __init__(self, app):
        self.app = app
        self.token = os.environ.get("MCP_AUTH_TOKEN")

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        # Allow /health without auth
        if scope["type"] == "http" and scope.get("path") == "/health":
            response = {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")]
            }
            await send(response)
            await send({
                "type": "http.response.body",
                "body": b"OK",
            })
            return

        if not self.token:
            # If no token configured, allow access
            return await self.app(scope, receive, send)
            
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        
        expected = f"Bearer {self.token}"
        if auth_header != expected:
            if scope["type"] == "http":
                response = {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"text/plain")]
                }
                await send(response)
                await send({
                    "type": "http.response.body",
                    "body": b"Unauthorized: Invalid or missing token",
                })
            elif scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
            
        return await self.app(scope, receive, send)

if __name__ == "__main__":
    import sys
    
    # Default: run with SSE transport (standard MCP)
    # Use --http flag to run with streamable-http transport via uvicorn + auth
    if "--http" in sys.argv:
        import uvicorn
        try:
            # FastMCP exposes an ASGI app for streamable-http
            asgi_app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.streamable_http_app()
            app = AuthMiddleware(asgi_app)
            print("Starting MCP server with HTTP transport + auth middleware on :8001")
            uvicorn.run(app, host="0.0.0.0", port=8001)
        except Exception as e:
            print(f"HTTP transport failed ({e}), falling back to SSE transport...")
            mcp.run(transport="sse")
    else:
        # Standard SSE transport — works with all MCP clients
        print("Starting MCP server with SSE transport on default port...")
        mcp.run(transport="sse")
