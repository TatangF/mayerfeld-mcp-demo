import pytest

gr = pytest.importorskip("gradio")


def test_ui_builds():
    from mayerfeld_mcp.ui import build_ui

    assert isinstance(build_ui(), gr.Blocks)
