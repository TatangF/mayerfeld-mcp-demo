"""Client MCP minimal (sans LLM) : montre le protocole brut.

initialize -> tools/list -> tools/call
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client


def unwrap(exc: BaseException) -> BaseException:
    """Remonte l'erreur réelle d'un ExceptionGroup (les task groups anyio emballent toute erreur)."""
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    return exc


def text_of(result) -> str:
    """Joint tous les blocs texte d'un résultat d'outil (une liste = plusieurs blocs)."""
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


def server_params(read_only: bool | None = None) -> StdioServerParameters:
    """Paramètres de lancement du serveur.

    Le SDK ne transmet au sous-processus qu'un environnement minimal (HOME, PATH...) :
    on passe donc explicitement le sandbox (chemin absolu) et le mode lecture seule.
    """
    if read_only is None:  # sans consigne explicite : on suit la variable MCP_READ_ONLY
        read_only = os.environ.get("MCP_READ_ONLY", "0").strip().lower() in {"1", "true", "yes"}
    sandbox = Path(os.environ.get("MCP_SANDBOX_DIR", "./sandbox")).resolve()
    env = {
        **get_default_environment(),
        "MCP_SANDBOX_DIR": str(sandbox),
        "MCP_READ_ONLY": "1" if read_only else "0",
    }
    return StdioServerParameters(command=sys.executable, args=["-m", "mayerfeld_mcp.server"], env=env)


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
