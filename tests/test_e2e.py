import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.fixture
def params(tmp_path):
    (tmp_path / "a.txt").write_text("Bonjour TODO\nligne 2", encoding="utf-8")
    env = {**os.environ, "MCP_SANDBOX_DIR": str(tmp_path)}
    return StdioServerParameters(command=sys.executable, args=["-m", "mayerfeld_mcp.server"], env=env)


def text_of(res):
    """Une liste renvoyée par un outil arrive en plusieurs blocs de contenu : on les joint."""
    return "\n".join(c.text for c in res.content if getattr(c, "text", None))


async def _call(params, name, args):
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await s.call_tool(name, args)


async def test_tools_discovered(params):
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
    assert names == {"list_files", "read_file", "write_file", "search_files"}


async def test_read_and_search(params):
    res = await _call(params, "read_file", {"path": "a.txt"})
    assert "Bonjour" in text_of(res)
    res = await _call(params, "search_files", {"query": "todo"})
    assert "a.txt:1" in text_of(res)


async def test_write_then_list(params):
    await _call(params, "write_file", {"path": "sub/b.txt", "content": "x"})
    res = await _call(params, "list_files", {})
    assert "b.txt" in text_of(res)


async def test_path_traversal_blocked(params):
    res = await _call(params, "read_file", {"path": "../../etc/passwd"})
    assert res.isError
