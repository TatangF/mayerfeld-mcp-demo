"""Agent LLM (Gemini Flash, offre gratuite) branché sur le serveur MCP.

Le modèle reçoit la liste des outils (nom, description, schéma JSON) découverte via MCP
et décide lui-même lequel appeler. Boucle : modèle -> function_call -> MCP -> résultat -> modèle.

Usage : mayerfeld-mcp-agent "Liste mes fichiers et résume taches.md"
Variables : GEMINI_API_KEY (obligatoire), GEMINI_MODEL (voir .env.example).
"""
from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from mayerfeld_mcp.client import server_params, text_of, unwrap

MAX_TURNS = 8
DEFAULT_MODEL = "gemini-2.5-flash"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # python-dotenv est optionnel ici
        pass


async def _run(prompt: str, client=None, read_only: bool | None = None, on_call=None) -> str:
    """Exécute la boucle agent.

    `client` peut être injecté pour les tests ; `on_call(name, args, result)` reçoit chaque appel d'outil
    (utilisé par l'interface graphique pour afficher la trace).
    """
    from google.genai import types

    _load_env()
    if client is None:
        from google import genai

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY manquante (voir .env.example).")
        client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    async with stdio_client(server_params(read_only=read_only)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            declarations = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description or "",
                    parameters_json_schema=t.inputSchema,
                )
                for t in listed.tools
            ]
            config = types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=declarations)],
                # On pilote la boucle nous-mêmes pour afficher chaque appel d'outil.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )
            contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

            for _ in range(MAX_TURNS):
                resp = await client.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
                calls = resp.function_calls or []
                if not calls:
                    return resp.text or ""
                contents.append(resp.candidates[0].content)
                parts = []
                for call in calls:
                    args = dict(call.args or {})
                    print(f"[outil] {call.name}({args})", file=sys.stderr)
                    out = await session.call_tool(call.name, args)
                    text = text_of(out)
                    payload = {"error": text} if out.isError else {"result": text}
                    if on_call:
                        on_call(call.name, args, text)
                    parts.append(types.Part.from_function_response(name=call.name, response=payload))
                contents.append(types.Content(role="user", parts=parts))
            return "Arrêt : nombre maximal de tours atteint."


async def run(prompt: str, client=None, read_only: bool | None = None, on_call=None) -> str:
    """Comme _run, mais lève l'erreur réelle (API Gemini, serveur...) au lieu d'un ExceptionGroup."""
    try:
        return await _run(prompt, client=client, read_only=read_only, on_call=on_call)
    except Exception as exc:
        leaf = unwrap(exc)
        if leaf is exc:
            raise
        raise leaf from None


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage : mayerfeld-mcp-agent "ta demande"')
    try:
        print(asyncio.run(run(" ".join(sys.argv[1:]))))
    except Exception as exc:  # erreurs API (quota, modèle inconnu…) lisibles pour la démo
        from google.genai import errors

        if isinstance(exc, errors.APIError):
            sys.exit(f"Erreur API Gemini {exc.code} : {exc.message}")
        raise


if __name__ == "__main__":
    main()
