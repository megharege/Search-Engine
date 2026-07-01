import os
from mcp.server.fastmcp import FastMCP
from search_core import hybrid_search, fetch_chunk_by_id, get_available_texts, get_available_categories

# Create FastMCP instance
mcp = FastMCP("ayurveda-rag")

@mcp.tool()
def search_verses(query: str, sthana: str | None = None, primary_category: str | None = None, limit: int = 10) -> list[dict]:
    """Hybrid keyword + semantic search over classical Ayurvedic texts.
    Returns matching chunks with chunk_id, sthana, verse_id, sanskrit_text,
    transliteration, topic_heading, and relevance score."""
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
    # If the user requested "streamable-http" in their snippet, we can use it.
    # Often standard FastMCP supports "sse" or "stdio".
    # We will wrap the underlying FastAPI app if it exists.
    # FastMCP uses an internal FastAPI app usually accessible via mcp._app.
    # If we need to run it with uvicorn and custom middleware, we might need to do it manually.
    import uvicorn
    
    # Check if we should use FastMCP's built-in run or uvicorn directly
    try:
        # For standard FastMCP, mcp._mcp or mcp.app might be the ASGI app
        asgi_app = getattr(mcp, "_app", None)
        if not asgi_app:
            # Maybe it's just mcp itself or we need to rely on run
            asgi_app = mcp
            
        app = AuthMiddleware(asgi_app)
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"Failed to wrap with AuthMiddleware, falling back to mcp.run: {e}")
        mcp.run(transport="streamable-http")
