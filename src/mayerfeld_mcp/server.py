"""Serveur MCP : accès fichiers limité à un dossier sandbox.

Lancement (stdio) : mayerfeld-mcp-server
Le dossier exposé est défini par MCP_SANDBOX_DIR (défaut : ./sandbox).
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

MAX_READ_BYTES = 100_000

mcp = FastMCP("mayerfeld-files")


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


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Crée ou remplace un fichier texte dans le sandbox."""
    target = _safe(path)
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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
