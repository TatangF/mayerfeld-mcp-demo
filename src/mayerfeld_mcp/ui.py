"""Interface graphique Gradio : tester les outils MCP, l'agent Gemini et le sandbox.

Lancement : mayerfeld-mcp-ui   (écoute sur 127.0.0.1 par défaut)
Variables : UI_HOST, UI_PORT, UI_USERNAME, UI_PASSWORD (voir .env.example).
"""
from __future__ import annotations

import os
import sys

import gradio as gr

from mayerfeld_mcp import service
from mayerfeld_mcp.client import unwrap

LIMITER = service.RateLimiter(max_calls=10, per_seconds=60)


def _err(exc: Exception) -> str:
    """Message d'erreur lisible, sans fuite de la clé API."""
    exc = unwrap(exc)  # l'erreur réelle, pas l'ExceptionGroup qui l'emballe
    if isinstance(exc, ValueError):
        return f"⚠️ {service.redact(str(exc))}"
    return f"⚠️ {type(exc).__name__} : {service.redact(str(exc))[:300]}"


# ---------- onglet 1 : outils MCP sans IA ----------
async def on_discover(read_only: bool):
    try:
        tools = await service.discover_tools(read_only)
    except Exception as exc:
        return [], [], gr.Dropdown(choices=[], value=None), _err(exc)
    rows = [[t["name"], t["description"]] for t in tools]
    names = [t["name"] for t in tools]
    status = f"✅ {len(tools)} outil(s) découvert(s) via tools/list"
    return rows, tools, gr.Dropdown(choices=names, value=names[0] if names else None), status


def on_select(tools: list[dict], name: str | None):
    for t in tools or []:
        if t["name"] == name:
            return t["schema"]
    return {}


async def on_call(name: str | None, raw_args: str, read_only: bool):
    if not name:
        return "⚠️ Découvre d'abord les outils, puis choisis-en un."
    try:
        return await service.call_tool(name, raw_args, read_only)
    except Exception as exc:
        return _err(exc)


# ---------- onglet 2 : agent ----------
async def on_agent(prompt: str, read_only: bool):
    try:
        answer, trace = await service.ask_agent(prompt, read_only, LIMITER)
        return answer, trace
    except Exception as exc:
        return _err(exc), ""


# ---------- onglet 3 : sandbox ----------
def on_refresh():
    rows = service.list_sandbox()
    names = [r[0] for r in rows]
    return rows, gr.Dropdown(choices=names, value=None), ""


def on_view(name: str | None):
    try:
        return service.read_sandbox_file(name)
    except Exception as exc:
        return _err(exc)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="MCP demo · mayerfeld.consulting") as demo:
        gr.Markdown(
            "# Démo MCP · mayerfeld.consulting\n"
            "⚠️ **Données jetables uniquement.** Le serveur est limité au dossier `sandbox/`."
        )
        read_only = gr.Checkbox(
            value=True,
            label="Mode lecture seule (recommandé) : l'outil write_file n'est pas exposé au modèle",
        )
        tools_state = gr.State([])

        with gr.Tab("1 · Outils MCP (sans IA)"):
            gr.Markdown("Le protocole brut : `tools/list` puis `tools/call`, sans modèle.")
            discover_btn = gr.Button("Découvrir les outils (tools/list)", variant="primary")
            status = gr.Markdown()
            table = gr.Dataframe(headers=["Outil", "Description"], interactive=False, wrap=True)
            tool_dd = gr.Dropdown(label="Outil", choices=[], interactive=True)
            schema = gr.JSON(label="Schéma d'entrée (JSON Schema)")
            args_box = gr.Textbox(label="Arguments (JSON)", value='{"path": "notes.txt"}', lines=3)
            call_btn = gr.Button("Appeler l'outil (tools/call)")
            result = gr.Textbox(label="Résultat", lines=8, interactive=False)

            discover_btn.click(on_discover, read_only, [table, tools_state, tool_dd, status], concurrency_limit=1)
            tool_dd.change(on_select, [tools_state, tool_dd], schema)
            call_btn.click(on_call, [tool_dd, args_box, read_only], result, concurrency_limit=1)

        with gr.Tab("2 · Agent Gemini"):
            gr.Markdown("Le modèle choisit lui-même les outils. La trace montre chaque appel réel.")
            prompt = gr.Textbox(
                label="Demande", lines=3, max_length=service.MAX_PROMPT_CHARS,
                value="Liste mes fichiers et résume taches.md",
            )
            run_btn = gr.Button("Lancer l'agent", variant="primary")
            answer = gr.Textbox(label="Réponse de Gemini", lines=6, interactive=False)
            trace = gr.Textbox(label="Trace des appels d'outils", lines=8, interactive=False)
            run_btn.click(on_agent, [prompt, read_only], [answer, trace], concurrency_limit=1)

        with gr.Tab("3 · Sandbox"):
            gr.Markdown("Vérifie les effets réels des outils sur le dossier `sandbox/`.")
            refresh_btn = gr.Button("Rafraîchir")
            files = gr.Dataframe(headers=["Fichier", "Taille (octets)"], interactive=False)
            file_dd = gr.Dropdown(label="Ouvrir un fichier", choices=[])
            content = gr.Textbox(label="Contenu", lines=10, interactive=False)
            refresh_btn.click(on_refresh, None, [files, file_dd, content])
            file_dd.change(on_view, file_dd, content)

    return demo


def main() -> None:
    from mayerfeld_mcp.agent import _load_env

    _load_env()
    host = os.environ.get("UI_HOST", "127.0.0.1")
    port = int(os.environ.get("UI_PORT", "7860"))
    user = os.environ.get("UI_USERNAME") or None
    pwd = os.environ.get("UI_PASSWORD") or None
    try:
        service.validate_launch(host, user, pwd)
    except ValueError as exc:
        sys.exit(f"Lancement refusé : {exc}")
    # share=False : jamais de lien public Gradio.
    build_ui().launch(
        server_name=host, server_port=port, share=False,
        auth=(user, pwd) if user and pwd else None,
    )


if __name__ == "__main__":
    main()
