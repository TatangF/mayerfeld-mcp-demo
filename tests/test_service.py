import pytest

from mayerfeld_mcp import service


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("bonjour", encoding="utf-8")
    monkeypatch.setenv("MCP_SANDBOX_DIR", str(tmp_path))
    return tmp_path


async def test_discover_respects_read_only(sandbox):
    assert {t["name"] for t in await service.discover_tools(False)} >= {"write_file"}
    assert "write_file" not in {t["name"] for t in await service.discover_tools(True)}


async def test_call_tool_ok_and_errors(sandbox):
    assert "bonjour" in await service.call_tool("read_file", '{"path": "a.txt"}', False)
    assert (await service.call_tool("read_file", '{"path": "../x"}', False)).startswith("[ERREUR]")
    with pytest.raises(ValueError):
        await service.call_tool("write_file", '{"path": "b.txt", "content": "x"}', True)  # désactivé
    with pytest.raises(ValueError):
        await service.call_tool("rm_rf", "{}", False)  # outil inconnu


def test_sandbox_listing_and_view(sandbox):
    assert service.list_sandbox() == [["a.txt", 7]]
    assert service.read_sandbox_file("a.txt") == "bonjour"
    with pytest.raises(ValueError):
        service.read_sandbox_file("../../etc/passwd")


async def test_ask_agent_validations(sandbox, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(service, "_load_env", lambda: None)
    lim = service.RateLimiter()
    for bad in ["", "x" * 2001]:
        with pytest.raises(ValueError):
            await service.ask_agent(bad, True, lim)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await service.ask_agent("salut", True, lim)
