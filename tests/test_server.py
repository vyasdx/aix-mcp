"""End-to-end: start the server over stdio with the MCP client and call every tool."""

import json
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

DATA = Path(__file__).parent / "data"


def _payload(result):
    assert not result.isError, result.content
    if result.structuredContent is not None:
        sc = result.structuredContent
        return sc.get("result", sc)
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_tools_over_stdio():
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "aix_mcp", "serve", "--evidence-dir", str(DATA)],
                                   env=dict(os.environ))
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = {t.name: t for t in (await s.list_tools()).tools}
        assert set(tools) == {"list_hosts", "lpar_identity", "findings", "path_health",
                              "missing_checks", "host_storage"}
        assert all(t.annotations and t.annotations.readOnlyHint for t in tools.values())

        hosts = _payload(await s.call_tool("list_hosts", {}))
        assert [h["host"] for h in hosts] == ["host-01", "vios-01"]

        high = _payload(await s.call_tool("findings", {"min_severity": "high"}))
        assert {(f["host"], f["subject"]) for f in high} == {("host-01", "hdisk1")}

        paths = _payload(await s.call_tool("path_health", {}))
        assert {p["disk"] for p in paths} == {"hdisk1", "hdisk2"}

        missing = _payload(await s.call_tool("missing_checks", {"host": "host-01"}))
        assert missing[0]["command"] == "bootinfo -s hdisk2"

        part = _payload(await s.call_tool("host_storage", {"host": "vios-01",
                                                           "sections": ["npiv_maps"]}))
        assert set(part) == {"source", "header", "npiv_maps"}

        bad = await s.call_tool("lpar_identity", {"host": "../etc"})
        assert bad.isError


@pytest.fixture
def anyio_backend():
    return "asyncio"
