"""Teste la boucle agent avec un faux client Gemini (aucune clé ni réseau requis)."""
import os
from types import SimpleNamespace

from mayerfeld_mcp.agent import run


class FakeModels:
    def __init__(self):
        self.calls = 0

    async def generate_content(self, model, contents, config):
        self.calls += 1
        if self.calls == 1:
            call = SimpleNamespace(name="list_files", args={})
            return SimpleNamespace(
                function_calls=[call],
                text=None,
                candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
            )
        last = contents[-1].parts[0].function_response
        assert last.name == "list_files" and "notes.txt" in last.response["result"]
        return SimpleNamespace(function_calls=None, text="OK", candidates=[])


async def test_agent_loop_calls_mcp_tool(monkeypatch):
    monkeypatch.setenv("MCP_SANDBOX_DIR", os.path.abspath("sandbox"))
    fake = SimpleNamespace(aio=SimpleNamespace(models=FakeModels()))
    assert await run("liste mes fichiers", client=fake) == "OK"


class BoomModels:
    async def generate_content(self, model, contents, config):
        raise RuntimeError("quota depasse")


async def test_agent_surfaces_real_error_not_exception_group(monkeypatch):
    import pytest

    monkeypatch.setenv("MCP_SANDBOX_DIR", os.path.abspath("sandbox"))
    fake = SimpleNamespace(aio=SimpleNamespace(models=BoomModels()))
    with pytest.raises(RuntimeError, match="quota depasse"):
        await run("salut", client=fake)


async def test_ui_error_message_shows_real_cause(monkeypatch):
    from mayerfeld_mcp.ui import _err

    monkeypatch.setenv("MCP_SANDBOX_DIR", os.path.abspath("sandbox"))
    fake = SimpleNamespace(aio=SimpleNamespace(models=BoomModels()))
    try:
        await run("salut", client=fake)
    except Exception as exc:
        assert "quota depasse" in _err(exc) and "ExceptionGroup" not in _err(exc)
