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