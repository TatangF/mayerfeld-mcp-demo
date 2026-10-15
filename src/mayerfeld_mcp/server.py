"""Serveur MCP : accès fichiers limité à un dossier sandbox.

Lancement (stdio) : mayerfeld-mcp-server
Le dossier exposé est défini par MCP_SANDBOX_DIR (défaut : ./sandbox).
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

MAX_READ_BYTES = 100_000
MAX_WRITE_BYTES = 100_000
# Extensions autorisées en écriture : on refuse tout le reste (.py, .exe, .bat...).
ALLOWED_WRITE_SUFFIXES = {".txt", ".md", ".json", ".csv"}

mcp = FastMCP("mayerfeld-files")


def read_only() -> bool:
    """Mode lecture seule : MCP_READ_ONLY=1 retire l'outil write_file."""
    return os.environ.get("MCP_READ_ONLY", "0").strip().lower() in {"1", "true", "yes"}


def _root() -> Path:
    return Path(os.environ.get("MCP_SANDBOX_DIR", "./sandbox")).resolve()


def _safe(relative: str) -> Path:
    """Résout un chemin relatif en refusant toute sortie du sandbox."""
    root = _root()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Chemin refusé : en dehors du dossier sandbox.")
    return target


@mcp.tool()
def list_files(subdir: str = ".") -> list[str]:
    """Liste les fichiers du sandbox (chemins relatifs), éventuellement dans un sous-dossier."""
    base = _safe(subdir)
    if not base.is_dir():
        raise ValueError(f"Dossier introuvable : {subdir}")
    root = _root()
    return sorted(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())


@mcp.tool()
def read_file(path: str) -> str:
    """Lit un fichier texte du sandbox (tronqué à 100 Ko)."""
    target = _safe(path)
    if not target.is_file():
        raise ValueError(f"Fichier introuvable : {path}")
    return target.read_bytes()[:MAX_READ_BYTES].decode("utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    """Crée ou remplace un fichier texte (.txt .md .json .csv) dans le sandbox."""
    target = _safe(path)
    if target.suffix.lower() not in ALLOWED_WRITE_SUFFIXES:
        raise ValueError(f"Extension refusée. Autorisées : {sorted(ALLOWED_WRITE_SUFFIXES)}")
    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        raise ValueError(f"Contenu trop volumineux (max {MAX_WRITE_BYTES} octets).")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Écrit {len(content)} caractères dans {path}"


@mcp.tool()
def search_files(query: str) -> list[str]:
    """Cherche un texte (insensible à la casse) dans les fichiers du sandbox ; renvoie 'fichier:ligne: texte'."""
    root = _root()
    needle = query.lower()
    hits: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            if needle in line.lower():
                hits.append(f"{p.relative_to(root)}:{i}: {line.strip()}")
    return hits


# write_file n'est enregistré que si le mode lecture seule est désactivé :
# un outil absent ne peut ni être appelé ni être suggéré au modèle (moindre privilège).
if not read_only():
    mcp.tool()(write_file)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
