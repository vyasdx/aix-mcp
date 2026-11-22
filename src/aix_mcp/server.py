"""MCP server for the AIX guest OS (evidence mode).

v0.1 reads collector output (``*.kh`` files) from an evidence directory on the
management tier. It never connects to AIX itself and has no tool that runs a
command. Collection over SSH with a forced-command dispatcher is on the roadmap
(docs/roadmap.md).

Every tool is read-only and returns compact, typed JSON so that an agent can
filter and join results (for example with HMC-level data on partition id).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import __version__
from .findings import SEVERITY_ORDER, all_findings
from .records import Collection, load_dir, to_dict

INSTRUCTIONS = """\
Read-only view of AIX LPARs and VIOS partitions, built from collector evidence.
Start with list_hosts. Use findings or path_health for estate-wide questions; they
filter on the server so results stay small. Every answer carries collected_at:
say how old the evidence is. A check marked MISSING means the data was not
collected (slow, hung or stale command); never treat missing data as healthy.
Join with HMC-level tools on machine_type_model + machine_serial + partition_id.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                            idempotentHint=True, openWorldHint=False)
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Evidence:
    """Loads the evidence directory and reloads it when files change."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self._stamp: tuple[int, float] | None = None
        self._hosts: dict[str, Collection] = {}

    def _current_stamp(self) -> tuple[int, float]:
        files = list(self.directory.rglob("*.kh")) if self.directory.is_dir() else []
        return len(files), max((f.stat().st_mtime for f in files), default=0.0)

    def hosts(self) -> dict[str, Collection]:
        stamp = self._current_stamp()
        if stamp != self._stamp:
            self._hosts = load_dir(self.directory) if self.directory.is_dir() else {}
            self._stamp = stamp
        return self._hosts

    def host(self, name: str) -> Collection:
        if not _HOST_RE.match(name or ""):
            raise ValueError("host must be a short host name (letters, digits, . _ -)")
        col = self.hosts().get(name)
        if col is None:
            raise ValueError(f"no evidence for host {name!r}; call list_hosts")
        return col

    def select(self, host: str | None) -> list[Collection]:
        return [self.host(host)] if host else list(self.hosts().values())


def build_server(evidence_dir: str | Path) -> FastMCP:
    ev = Evidence(evidence_dir)
    mcp = FastMCP("aix-mcp", instructions=INSTRUCTIONS)

    @mcp.tool(annotations=READ_ONLY)
    def list_hosts() -> list[dict[str, Any]]:
        """List hosts with evidence: role, AIX level, LPAR identity, age and check counts."""
        out = []
        for col in sorted(ev.hosts().values(), key=lambda c: c.host):
            ident = col.identity()
            ident.update({
                "collected_at": col.collected_at,
                "multipath": col.header.get("multipath"),
                "checks": col.header.get("checks"),
            })
            out.append(ident)
        return out

    @mcp.tool(annotations=READ_ONLY)
    def lpar_identity(host: str) -> dict[str, Any]:
        """Partition id/name, machine type-model and serial for one host.
        Use it to join with HMC or PowerVS data about the same LPAR."""
        return ev.host(host).identity()

    @mcp.tool(annotations=READ_ONLY)
    def findings(host: str | None = None, min_severity: str = "low",
                 min_enabled_paths: int = 2, used_pct: int = 90) -> list[dict[str, Any]]:
        """Storage and multipath findings for one host, or for every host when host is
        omitted. min_severity is info, low, medium or high. Each finding has evidence."""
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(f"min_severity must be one of {list(SEVERITY_ORDER)}")
        floor = SEVERITY_ORDER[min_severity]
        return [f for col in ev.select(host)
                for f in all_findings(col, min_enabled_paths, used_pct)
                if SEVERITY_ORDER[f["severity"]] >= floor]

    @mcp.tool(annotations=READ_ONLY)
    def path_health(host: str | None = None, only_problems: bool = True) -> list[dict[str, Any]]:
        """Per-disk path counts (total, Enabled, Failed, other, ALUA-optimised) and the
        multipath driver. Estate-wide when host is omitted; only_problems keeps disks
        with a non-Enabled path or a single path."""
        out = []
        for col in ev.select(host):
            for d in col.get("D"):
                bad = (d["failed"] or 0) + (d["other"] or 0)
                single = (d["paths"] or 0) == 1
                if only_problems and not (bad or single):
                    continue
                out.append({"host": col.host, "disk": d["disk"], "vg": d["vg"],
                            "driver": d["driver"], "paths": d["paths"], "enabled": d["enabled"],
                            "failed": d["failed"], "other": d["other"],
                            "optimised": d["optimised"], "collected_at": col.collected_at})
        return out

    @mcp.tool(annotations=READ_ONLY)
    def missing_checks(host: str | None = None) -> list[dict[str, Any]]:
        """Checks that did not answer (timeout, budget, refused) with the command to run
        by hand. Use it to say what is NOT known."""
        return [{"host": col.host, "check": c["check"], "status": c["status"],
                 "reason": c["reason"], "command": c["command"]}
                for col in ev.select(host) for c in col.get("C")
                if c["status"] in ("MISSING", "REFUSED")]

    @mcp.tool(annotations=READ_ONLY)
    def host_storage(host: str, sections: list[str] | None = None) -> dict[str, Any]:
        """Full storage evidence for one host. sections limits the output, for example
        ["disks","adapters","mounts","filesystems","npiv_maps","vscsi_maps","notes"]."""
        data = to_dict(ev.host(host))
        if sections:
            keep = set(sections) | {"source", "header"}
            data = {k: v for k, v in data.items() if k in keep}
        return data

    @mcp.resource("aix-mcp://about")
    def about() -> str:
        """What this server is and what it will never do."""
        return (f"aix-mcp {__version__}: read-only AIX guest-OS evidence server. "
                f"No command execution tools. Evidence directory: {ev.directory}")

    return mcp


def main_serve(evidence_dir: str | None = None) -> None:
    directory = evidence_dir or os.environ.get("AIX_MCP_EVIDENCE_DIR") or "./evidence"
    build_server(directory).run(transport="stdio")
