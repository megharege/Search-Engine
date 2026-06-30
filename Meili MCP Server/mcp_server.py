"""
Ayurveda Search – MCP Server
============================================================
Exposes the local Meilisearch index as MCP tools that any
compatible AI client (Claude Desktop, Cursor, Cline, etc.)
can call to search classical Ayurvedic texts.

Transport : stdio  (standard for local MCP servers)

Install dependencies (run once):
    pip install mcp meilisearch

Run the server manually (for testing):
    python mcp_server.py

Add to Claude Desktop config  (~/.claude/claude_desktop_config.json):
{
  "mcpServers": {
    "ayurveda_search": {
      "command": "python",
      "args": ["C:/Users/KIIT0001/OneDrive/Search Engine/ayurveda_meili/mcp_server.py"],
      "env": {}
    }
  }
}
============================================================
"""

import asyncio
import json
import meilisearch
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ─── Configuration ────────────────────────────────────────────────────────────
MEILI_URL        = "http://localhost:7700"
MEILI_KEY        = "ayurveda-dev-key"
MEILI_INDEX      = "ayurveda"

# ─── Meilisearch client ───────────────────────────────────────────────────────
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index  = client.index(MEILI_INDEX)

# ─── MCP Server ───────────────────────────────────────────────────────────────
app = Server("ayurveda-search")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_ayurveda",
            description=(
                "Search classical Ayurvedic texts (Sushruta Samhita, Ashtanga Hridaya, "
                "Madhavanidanam) using hybrid semantic + keyword search. "
                "Returns matching verses with Sanskrit text, transliteration, "
                "commentary, chapter info, and topic tags."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, e.g. 'vata dosha treatment' or 'jwara fever'"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["Hybrid", "Semantic", "Keyword"],
                        "description": "Search mode. Default is Hybrid (best of both worlds).",
                        "default": "Hybrid"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (1-100). Default is 10.",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "books": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "Sushruta Samhita",
                                "Ashtanga Hridaya",
                                "Madhavanisana Pt1",
                                "Madhavanisana Pt2"
                            ]
                        },
                        "description": "Filter results to specific books. Leave empty to search all.",
                        "default": []
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_ayurveda_stats",
            description=(
                "Get statistics about the Ayurveda Meilisearch index, "
                "including total number of indexed documents and index health."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "search_ayurveda":
        query = arguments.get("query", "").strip()
        mode  = arguments.get("mode", "Hybrid")
        limit = int(arguments.get("limit", 10))
        books = arguments.get("books", [])

        if not query:
            return [types.TextContent(type="text", text="Error: query is required.")]

        params = {
            "limit": limit,
            "attributesToHighlight": ["commentary", "transliteration", "topic_heading"],
            "highlightPreTag": "**",
            "highlightPostTag": "**",
        }

        if mode == "Hybrid":
            params["hybrid"] = {"semanticRatio": 0.5, "embedder": "default"}
        elif mode == "Semantic":
            params["hybrid"] = {"semanticRatio": 1.0, "embedder": "default"}

        if books:
            book_clause = " OR ".join([f'source_file = "{b}"' for b in books])
            params["filter"] = f"({book_clause})"

        try:
            results = index.search(query, params)
            hits    = results.get("hits", [])
            time_ms = results.get("processingTimeMs", 0)

            if not hits:
                return [types.TextContent(
                    type="text",
                    text=f"No results found for '{query}' in the Ayurveda index."
                )]

            output_lines = [
                f"# Ayurveda Search Results",
                f"**Query:** {query}  |  **Mode:** {mode}  |  **Results:** {len(hits)}  |  **Time:** {time_ms}ms",
                ""
            ]

            for i, hit in enumerate(hits, 1):
                fmt      = hit.get("_formatted", hit)
                source   = hit.get("source_file", "Unknown")
                sthana   = hit.get("sthana", "")
                ch_num   = hit.get("chapter_number", "")
                ch_title = hit.get("chapter_title", "")
                verse_id = hit.get("verse_id", "")
                topic    = fmt.get("topic_heading", "") or hit.get("topic_heading", "")
                sanskrit = hit.get("sanskrit_text", "")
                translit = fmt.get("transliteration", "") or hit.get("transliteration", "")
                comment  = fmt.get("commentary", "") or hit.get("commentary", "")
                cats     = hit.get("categories_found", []) or []
                primary  = hit.get("primary_category", "")

                header_parts = [source]
                if sthana:   header_parts.append(f"({sthana})")
                if ch_title: header_parts.append(f"Ch. {ch_num} \"{ch_title}\"")
                if verse_id: header_parts.append(f"Verse {verse_id}")

                tags = list(dict.fromkeys(filter(None, [primary] + cats)))

                output_lines += [
                    f"---",
                    f"## {i}. {topic or 'Verse'}",
                    f"*{' · '.join(header_parts)}*",
                ]
                if sanskrit:  output_lines.append(f"\n**Sanskrit:** {sanskrit}")
                if translit:  output_lines.append(f"**Transliteration:** {translit}")
                if comment:   output_lines.append(f"\n**Commentary:** {comment}")
                if tags:      output_lines.append(f"\n**Topics:** {', '.join(tags)}")
                output_lines.append("")

            return [types.TextContent(type="text", text="\n".join(output_lines))]

        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error querying Meilisearch: {e}\n\nMake sure Meilisearch is running on {MEILI_URL}"
            )]

    elif name == "get_ayurveda_stats":
        try:
            stats = index.get_stats()
            info  = {
                "index"          : MEILI_INDEX,
                "total_documents": stats.number_of_documents,
                "is_indexing"    : stats.is_indexing,
                "field_counts"   : dict(list(stats.field_distribution.items())[:10])
            }
            text = (
                f"# Ayurveda Index Statistics\n\n"
                f"- **Index Name:** {info['index']}\n"
                f"- **Total Documents:** {info['total_documents']:,}\n"
                f"- **Currently Indexing:** {'Yes' if info['is_indexing'] else 'No'}\n\n"
                f"**Top Fields:**\n"
                + "\n".join(f"  - `{k}`: {v} docs" for k, v in info["field_counts"].items())
            )
            return [types.TextContent(type="text", text=text)]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error fetching stats: {e}"
            )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
