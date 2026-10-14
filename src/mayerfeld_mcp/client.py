"""Client MCP minimal (sans LLM) : montre le protocole brut.

initialize -> tools/list -> tools/call
"""
from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def text_of(result) -> str:
    """Joint tous les blocs texte d'un résultat d'outil (une liste = plusieurs blocs)."""
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


def server_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "mayerfeld_mcp.server"])


async def demo() -> None:
    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== Outils découverts ==")
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")

            print("\n== list_files ==")
            res = await session.call_tool("list_files", {})
            print(text_of(res))

            print("\n== search_files('TODO') ==")
            res = await session.call_tool("search_files", {"query": "TODO"})
            print(text_of(res))


def main() -> None:
    asyncio.run(demo())


if __name__ == "__main__":
    main()
