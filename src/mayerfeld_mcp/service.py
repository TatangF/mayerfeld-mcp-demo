"""Couche de service de l'interface graphique : logique + sécurité, testable sans navigateur.

L'interface (ui.py) ne contient que de l'affichage ; tout ce qui touche à MCP, aux
validations et aux limites vit ici.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from mayerfeld_mcp import server as server_module
from mayerfeld_mcp.agent import _load_env, run
from mayerfeld_mcp.client import server_params, text_of

MAX_PROMPT_CHARS = 2_000
MAX_ARGS_CHARS = 20_000
MAX_VIEW_BYTES = 100_000
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
MIN_PASSWORD_LEN = 8


# ---------- sécurité : lancement, limites, secrets ----------
def validate_launch(host: str, username: str | None, password: str | None) -> None:
    """Refuse un lancement dangereux : exposition réseau sans mot de passe, ou mot de passe trop court."""
    if password and len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"UI_PASSWORD trop court (minimum {MIN_PASSWORD_LEN} caractères).")
    if bool(username) != bool(password):
        raise ValueError("Renseigne UI_USERNAME et UI_PASSWORD ensemble, ou aucun des deux.")
    if host not in LOCAL_HOSTS and not (username and password):
        raise ValueError(
            f"UI_HOST={host} expose l'interface au réseau : UI_USERNAME et UI_PASSWORD sont obligatoires."
        )


class RateLimiter:
    """Limite le nombre d'appels à l'agent (protège le quota gratuit et la clé)."""

    def __init__(self, max_calls: int = 10, per_seconds: float = 60.0):
        self.max_calls, self.per_seconds = max_calls, per_seconds
        self._calls: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > self.per_seconds:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True


def redact(text: str) -> str:
    """Masque la clé API si elle apparaît dans un message d'erreur."""
    key = os.environ.get("GEMINI_API_KEY")
    return text.replace(key, "***") if key else text


def parse_args(raw: str | None) -> dict:
    raw = (raw or "").strip() or "{}"
    if len(raw) > MAX_ARGS_CHARS:
        raise ValueError("Arguments trop volumineux.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide : {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Les arguments doivent être un objet JSON, ex. {\"path\": \"notes.txt\"}.")
    return data


# ---------- MCP ----------
@asynccontextmanager
async def open_session(read_only: bool):
    """Lance le serveur MCP en sous-processus, ouvre une session, la ferme proprement."""
    async with stdio_client(server_params(read_only=read_only)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools(read_only: bool) -> list[dict]:
    async with open_session(read_only) as session:
        listed = await session.list_tools()
    return [
        {"name": t.name, "description": t.description or "", "schema": t.inputSchema}
        for t in listed.tools
    ]


async def call_tool(name: str, raw_args: str | None, read_only: bool) -> str:
    args = parse_args(raw_args)
    out = None
    async with open_session(read_only) as session:
        known = {t.name for t in (await session.list_tools()).tools}
        if name in known:
            out = await session.call_tool(name, args)
    # On lève l'erreur APRÈS la fermeture de la session : une exception levée à l'intérieur
    # ressortirait enveloppée dans un ExceptionGroup (task groups anyio) et serait illisible.
    if out is None:
        raise ValueError(f"Outil inconnu ou désactivé : {name!r}")
    return ("[ERREUR] " if out.isError else "") + text_of(out)


async def ask_agent(prompt: str, read_only: bool, limiter: RateLimiter) -> tuple[str, str]:
    """Valide la demande, applique la limite, lance l'agent. Renvoie (réponse, trace des outils)."""
    _load_env()
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Saisis une demande.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"Demande trop longue (max {MAX_PROMPT_CHARS} caractères).")
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY manquante : renseigne-la dans .env (voir README).")
    if not limiter.allow():
        raise ValueError("Trop de demandes : attends une minute (limite de protection du quota).")

    trace: list[str] = []

    def on_call(name: str, args: dict, result: str) -> None:
        preview = result if len(result) <= 300 else result[:300] + "…"
        trace.append(f"[outil] {name}({args})\n   → {preview}")

    answer = await run(prompt, read_only=read_only, on_call=on_call)
    return answer, "\n".join(trace) or "(aucun outil appelé)"


# ---------- sandbox (lecture locale, indépendante de MCP) ----------
def list_sandbox() -> list[list]:
    root = server_module._root()
    if not root.is_dir():
        return []
    return [
        [str(p.relative_to(root)), p.stat().st_size]
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]


def read_sandbox_file(relative: str | None) -> str:
    if not relative:
        return ""
    target = server_module._safe(relative)  # même garde-fou que le serveur
    if not target.is_file():
        raise ValueError("Fichier introuvable.")
    return target.read_bytes()[:MAX_VIEW_BYTES].decode("utf-8", errors="replace")
