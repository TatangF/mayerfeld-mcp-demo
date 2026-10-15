import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mayerfeld_mcp import service
from mayerfeld_mcp.client import server_params


def _params(tmp_path, **extra):
    env = {**os.environ, "MCP_SANDBOX_DIR": str(tmp_path), **extra}
    return StdioServerParameters(command=sys.executable, args=["-m", "mayerfeld_mcp.server"], env=env)


async def _tools(params):
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return {t.name for t in (await s.list_tools()).tools}


async def _call(params, name, args):
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await s.call_tool(name, args)


# ---- serveur ----
async def test_read_only_hides_write_tool(tmp_path):
    assert "write_file" not in await _tools(_params(tmp_path, MCP_READ_ONLY="1"))
    assert "write_file" in await _tools(_params(tmp_path, MCP_READ_ONLY="0"))


async def test_write_rejects_bad_extension(tmp_path):
    res = await _call(_params(tmp_path), "write_file", {"path": "evil.py", "content": "print(1)"})
    assert res.isError and not (tmp_path / "evil.py").exists()


async def test_write_rejects_oversize(tmp_path):
    res = await _call(_params(tmp_path), "write_file", {"path": "big.txt", "content": "x" * 100_001})
    assert res.isError and not (tmp_path / "big.txt").exists()


# ---- client : le sandbox et le mode lecture seule sont bien transmis au sous-processus ----
def test_server_params_pass_explicit_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_SANDBOX_DIR", str(tmp_path))
    env = server_params(read_only=True).env
    assert env["MCP_SANDBOX_DIR"] == str(tmp_path.resolve())
    assert env["MCP_READ_ONLY"] == "1"


# ---- couche de service ----
def test_validate_launch():
    service.validate_launch("127.0.0.1", None, None)  # local sans mot de passe : OK
    service.validate_launch("0.0.0.0", "admin", "motdepasse-long")  # réseau + mot de passe : OK
    with pytest.raises(ValueError):
        service.validate_launch("0.0.0.0", None, None)  # réseau sans mot de passe
    with pytest.raises(ValueError):
        service.validate_launch("127.0.0.1", "admin", "court")  # mot de passe trop court
    with pytest.raises(ValueError):
        service.validate_launch("127.0.0.1", "admin", None)  # moitié des identifiants


def test_rate_limiter():
    lim = service.RateLimiter(max_calls=2, per_seconds=60)
    assert lim.allow() and lim.allow() and not lim.allow()


def test_parse_args():
    assert service.parse_args("") == {}
    assert service.parse_args('{"a": 1}') == {"a": 1}
    for bad in ["[1]", "{oups", "x" * 20_001]:
        with pytest.raises(ValueError):
            service.parse_args(bad)


def test_redact(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET123")
    assert "SECRET123" not in service.redact("erreur avec SECRET123 dedans")


def test_server_params_follow_env_when_unspecified(monkeypatch):
    monkeypatch.setenv("MCP_READ_ONLY", "1")
    assert server_params().env["MCP_READ_ONLY"] == "1"
    assert server_params(read_only=False).env["MCP_READ_ONLY"] == "0"  # l'argument explicite l'emporte
