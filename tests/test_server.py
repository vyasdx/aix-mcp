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
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
TOOLS = {"aix_list_hosts", "aix_lpar_identity", "aix_findings", "aix_path_health",
         "aix_missing_checks", "aix_host_storage"}


def _sc(result):
    assert not result.isError, result.content
    assert result.structuredContent is not None
    return result.structuredContent


@pytest.mark.anyio
async def test_tools_over_stdio(tmp_path):
    audit = tmp_path / "audit.jsonl"
    env = dict(os.environ, AIX_MCP_AUDIT_LOG=str(audit))
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "aix_mcp", "serve", "--evidence-dir", str(DATA)],
                                   env=env)
    with open(tmp_path / "stderr.txt", "w") as err:
        async with stdio_client(params, errlog=err) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name: t for t in (await s.list_tools()).tools}
            assert set(tools) == TOOLS
            for t in tools.values():
                assert t.annotations.readOnlyHint is True
                assert t.outputSchema and t.outputSchema.get("type") == "object", t.name

            hosts = _sc(await s.call_tool("aix_list_hosts", {}))
            assert hosts["schema_version"] == "1"
            assert [h["host"] for h in hosts["items"]] == ["host-01", "vios-01"]
            assert hosts["items"][0]["evidence_age_hours"] > 0

            high = _sc(await s.call_tool("aix_findings", {"min_severity": "high"},
                                         meta={"traceparent": TRACE}))
            assert [(f["host"], f["subject"]) for f in high["items"]] == [("host-01", "hdisk1")]

            only = _sc(await s.call_tool("aix_findings", {"finding_id": "vfchost_not_logged_in"}))
            assert [f["subject"] for f in only["items"]] == ["vfchost2"]

            paths = _sc(await s.call_tool("aix_path_health", {}))
            assert {p["disk"] for p in paths["items"]} == {"hdisk1", "hdisk2"}

            # paging: walk all findings one by one and compare with a single call
            full = _sc(await s.call_tool("aix_findings", {"min_severity": "info"}))
            seen, cursor = [], None
            while True:
                args = {"min_severity": "info", "limit": 1}
                if cursor:
                    args["cursor"] = cursor
                page = _sc(await s.call_tool("aix_findings", args))
                assert page["total"] == full["total"] and page["returned"] == 1
                seen += page["items"]
                cursor = page["next_cursor"]
                if not cursor:
                    break
            assert seen == full["items"]

            # a cursor is bound to its arguments
            first = _sc(await s.call_tool("aix_findings", {"min_severity": "info", "limit": 1}))
            wrong = await s.call_tool("aix_findings", {"min_severity": "low", "limit": 1,
                                                       "cursor": first["next_cursor"]})
            assert wrong.isError

            missing = _sc(await s.call_tool("aix_missing_checks", {"host": "host-01"}))
            assert missing["items"][0]["command"] == "bootinfo -s hdisk2"

            part = _sc(await s.call_tool("aix_host_storage", {"host": "vios-01",
                                                              "sections": ["npiv_maps"]}))
            assert set(part["sections"]) == {"npiv_maps"}

            ident = _sc(await s.call_tool("aix_lpar_identity", {"host": "host-01"}))
            assert (ident["machine_serial"], ident["partition_id"]) == ("02SYN0001", 5)

            assert (await s.call_tool("aix_lpar_identity", {"host": "../etc"})).isError
            assert (await s.call_tool("aix_findings", {"limit": 5000})).isError
            assert (await s.call_tool("aix_findings", {"min_severity": "urgent"})).isError

    lines = [json.loads(x) for x in audit.read_text().splitlines()]
    assert all(x["event"] == "tool_call" for x in lines)
    traced = [x for x in lines if x["traceparent"] == TRACE]
    assert len(traced) == 1 and traced[0]["tool"] == "aix_findings"
    assert any(x["error"] for x in lines if x["tool"] == "aix_lpar_identity")


@pytest.fixture
def anyio_backend():
    return "asyncio"
