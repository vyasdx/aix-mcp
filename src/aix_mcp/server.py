"""MCP server for the AIX guest OS (evidence mode).

v0.1 reads collector output (``*.kh`` files) from an evidence directory on the
management tier. It never connects to AIX itself and has no tool that runs a
command. Collection over SSH with a forced-command dispatcher is on the roadmap
(docs/roadmap.md).

Design rules (see docs/design.md):
* every tool is read-only and has a typed outputSchema (models.py);
* estate-wide questions are answered by filtering here, with limit + cursor;
* every call writes one audit line, carrying the caller's W3C traceparent from
  ``_meta`` when present, so the calls of one agent script can be tied together.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from . import __version__
from .findings import SEVERITY_ORDER, all_findings
from .models import (
    DiskPaths, Finding, FindingsPage, HostInfo, HostsPage, HostStorage, LparIdentity,
    MissingCheck, MissingPage, PathsPage, PerfDaySummary, PerfFinding, PerfFindingsPage,
    PerfPage, PerfRank, PerfRankMetric, PerfRankPage, Section, Severity,
)
from .perf import parse_nmon_file, perf_findings, summarise
from .records import Collection, load_dir, to_dict

INSTRUCTIONS = """\
Read-only view of AIX LPARs and VIOS partitions, built from collector evidence.
Start with aix_list_hosts. For estate-wide questions use aix_findings or
aix_path_health without a host: they filter here, so results stay small; follow
next_cursor for more. Every item carries evidence_age_hours: say how old the
evidence is. A check marked MISSING was not collected (slow, hung or stale
command); never treat missing data as healthy. Join with HMC-level tools on
machine_type_model + machine_serial + partition_id (aix_lpar_identity).
Performance history (aix_perf_*) comes from the AIX daily recording at 5-minute
intervals: aix_perf_top ranks the estate, aix_perf_summary covers one host.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                            idempotentHint=True, openWorldHint=False)
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")

audit_log = logging.getLogger("aix_mcp.audit")


def _setup_audit() -> None:
    if audit_log.handlers:
        return
    audit_log.setLevel(logging.INFO)
    audit_log.propagate = False
    # stdio servers must keep stdout for the protocol: audit goes to stderr and,
    # if AIX_MCP_AUDIT_LOG is set, to that file as JSON lines.
    audit_log.addHandler(logging.StreamHandler(sys.stderr))
    path = os.environ.get("AIX_MCP_AUDIT_LOG")
    if path:
        audit_log.addHandler(logging.FileHandler(path, encoding="utf-8"))


def _age_hours(collected_at: str) -> float | None:
    try:
        t = datetime.strptime(collected_at, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return round((datetime.now(timezone.utc) - t).total_seconds() / 3600, 1)


class Evidence:
    """Loads the evidence directory and reloads it when files change."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.stamp: tuple[int, float] | None = None
        self._hosts: dict[str, Collection] = {}
        self._perf: dict[str, list[dict[str, Any]]] = {}

    def _files(self, pattern: str) -> list[Path]:
        return list(self.directory.rglob(pattern)) if self.directory.is_dir() else []

    def _current_stamp(self) -> tuple[int, float]:
        files = self._files("*.kh") + self._files("*.nmon.csv") + self._files("*.nmon")
        return len(files), max((f.stat().st_mtime for f in files), default=0.0)

    def _refresh(self) -> None:
        stamp = self._current_stamp()
        if stamp == self.stamp:
            return
        self._hosts = load_dir(self.directory) if self.directory.is_dir() else {}
        perf: dict[str, dict[str, dict[str, Any]]] = {}
        for p in sorted(self._files("*.nmon.csv") + self._files("*.nmon")):
            day = parse_nmon_file(p)
            # files pulled by `aix-mcp collect` live in <evidence>/<host>/perf/
            host = p.parent.parent.name if p.parent.name == "perf" else (day.host or p.stem)
            if not day.date or not _HOST_RE.match(host):
                continue
            summ = summarise(day)
            summ["host"] = host
            old = perf.setdefault(host, {}).get(day.date)
            if old is None or summ["snapshots"] > old["snapshots"]:
                perf[host][day.date] = summ
        self._perf = {h: [d[k] for k in sorted(d)] for h, d in perf.items()}
        self.stamp = stamp

    def hosts(self) -> dict[str, Collection]:
        self._refresh()
        return self._hosts

    def perf_days(self, host: str | None, days: int) -> dict[str, list[dict[str, Any]]]:
        """Newest `days` daily summaries per host."""
        if not 1 <= days <= 92:
            raise ValueError("days must be between 1 and 92")
        self._refresh()
        if host:
            if not _HOST_RE.match(host):
                raise ValueError("host must be a short host name (letters, digits, . _ -)")
            if host not in self._perf:
                raise ValueError(f"no performance history for host {host!r}")
            return {host: self._perf[host][-days:]}
        return {h: v[-days:] for h, v in sorted(self._perf.items())}

    def host(self, name: str) -> Collection:
        if not _HOST_RE.match(name or ""):
            raise ValueError("host must be a short host name (letters, digits, . _ -)")
        col = self.hosts().get(name)
        if col is None:
            raise ValueError(f"no evidence for host {name!r}; call aix_list_hosts")
        return col

    def select(self, host: str | None) -> list[Collection]:
        if host:
            return [self.host(host)]
        return sorted(self.hosts().values(), key=lambda c: c.host)


def _query_key(tool: str, args: dict[str, Any], stamp: Any) -> str:
    raw = json.dumps([tool, args, stamp], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _page(items: list[Any], tool: str, args: dict[str, Any], stamp: Any,
          limit: int, cursor: str | None) -> tuple[list[Any], int, str | None]:
    """Slice items for one page. The cursor is bound to the tool, its other
    arguments and the evidence snapshot, so a stale or foreign cursor is refused."""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    key = _query_key(tool, args, stamp)
    offset = 0
    if cursor:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            offset, ckey = int(data["o"]), str(data["k"])
        except Exception:
            raise ValueError("cursor is not valid; start again without cursor") from None
        if ckey != key or offset < 0:
            raise ValueError("cursor does not match these arguments or the evidence changed; "
                             "start again without cursor")
    chunk = items[offset: offset + limit]
    nxt = None
    if offset + limit < len(items):
        nxt = base64.urlsafe_b64encode(
            json.dumps({"o": offset + limit, "k": key}).encode()).decode()
    return chunk, len(items), nxt


def _traceparent(ctx: Context | None) -> str | None:
    try:
        meta = ctx.request_context.meta if ctx else None
    except Exception:
        return None
    if meta is None:
        return None
    tp = getattr(meta, "traceparent", None) or (meta.model_extra or {}).get("traceparent")
    if tp is None:
        return None
    return tp if isinstance(tp, str) and _TRACEPARENT_RE.match(tp) else "invalid"


def _audit(ctx: Context | None, tool: str, args: dict[str, Any], t0: float,
           returned: int | None = None, error: str | None = None) -> None:
    audit_log.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": "tool_call",
        "tool": tool,
        "args": {k: v for k, v in args.items() if v is not None},
        "traceparent": _traceparent(ctx),
        "returned": returned,
        "error": error,
        "ms": round((time.monotonic() - t0) * 1000, 1),
    }, default=str))


def build_server(evidence_dir: str | Path) -> FastMCP:
    _setup_audit()
    ev = Evidence(evidence_dir)
    mcp = FastMCP("aix-mcp", instructions=INSTRUCTIONS)

    def run(ctx: Context | None, tool: str, args: dict[str, Any], fn):
        t0 = time.monotonic()
        try:
            out = fn()
        except Exception as e:
            _audit(ctx, tool, args, t0, error=str(e)[:200])
            raise
        _audit(ctx, tool, args, t0, returned=getattr(out, "returned", 1))
        return out

    def paged(model, items, tool, args, limit, cursor, hosts_considered, note=None, **extra):
        chunk, total, nxt = _page(items, tool, args, ev.stamp, limit, cursor)
        if nxt and note is None:
            note = f"{total} items; showing {len(chunk)}. Narrow with host or filters, or follow next_cursor."
        return model(total=total, returned=len(chunk), next_cursor=nxt,
                     hosts_considered=hosts_considered, note=note, items=chunk, **extra)

    @mcp.tool(annotations=READ_ONLY)
    def aix_list_hosts(ctx: Context, limit: int = DEFAULT_LIMIT,
                       cursor: str | None = None) -> HostsPage:
        """List hosts with evidence: role (LPAR/VIOS), AIX level, LPAR identity,
        evidence age and check counts."""
        args = {"limit": limit}

        def go():
            cols = ev.select(None)
            items = [HostInfo(**c.identity(), collected_at=c.collected_at,
                              evidence_age_hours=_age_hours(c.collected_at),
                              multipath=c.header.get("multipath"), checks=c.header.get("checks"))
                     for c in cols]
            return paged(HostsPage, items, "aix_list_hosts", args, limit, cursor, len(cols))
        return run(ctx, "aix_list_hosts", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_lpar_identity(ctx: Context, host: str) -> LparIdentity:
        """Partition id/name, machine type-model and serial for one host. Use it to join
        with HMC or PowerVS data about the same LPAR."""
        return run(ctx, "aix_lpar_identity", {"host": host},
                   lambda: LparIdentity(**ev.host(host).identity()))

    @mcp.tool(annotations=READ_ONLY)
    def aix_findings(ctx: Context, host: str | None = None, min_severity: Severity = "low",
                     finding_id: str | None = None, min_enabled_paths: int = 2,
                     used_pct: int = 90, limit: int = DEFAULT_LIMIT,
                     cursor: str | None = None) -> FindingsPage:
        """Storage, multipath, FC and VIOS findings with evidence, highest severity first.
        Whole estate when host is omitted. finding_id filters one type, e.g.
        path_not_enabled, too_few_paths, hcheck_disabled, fc_link_not_up,
        vfchost_not_logged_in, filesystem_used, check_missing."""
        args = {"host": host, "min_severity": min_severity, "finding_id": finding_id,
                "min_enabled_paths": min_enabled_paths, "used_pct": used_pct, "limit": limit}

        def go():
            floor = SEVERITY_ORDER[min_severity]
            cols = ev.select(host)
            items = [Finding(**f, evidence_age_hours=_age_hours(f["collected_at"]))
                     for c in cols for f in all_findings(c, min_enabled_paths, used_pct)
                     if SEVERITY_ORDER[f["severity"]] >= floor
                     and (finding_id is None or f["id"] == finding_id)]
            items.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.host, f.subject))
            return paged(FindingsPage, items, "aix_findings", args, limit, cursor, len(cols))
        return run(ctx, "aix_findings", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_path_health(ctx: Context, host: str | None = None, only_problems: bool = True,
                        min_enabled_paths: int = 2, limit: int = DEFAULT_LIMIT,
                        cursor: str | None = None) -> PathsPage:
        """Per-disk path counts (total, Enabled, Failed, other, ALUA-optimised) and the
        multipath driver. Whole estate when host is omitted. only_problems keeps disks
        with a non-Enabled path or fewer than min_enabled_paths Enabled paths."""
        args = {"host": host, "only_problems": only_problems,
                "min_enabled_paths": min_enabled_paths, "limit": limit}

        def go():
            cols = ev.select(host)
            items = []
            for c in cols:
                for d in c.get("D"):
                    bad = (d["failed"] or 0) + (d["other"] or 0)
                    few = (d["paths"] or 0) > 0 and (d["enabled"] or 0) < min_enabled_paths
                    if only_problems and not (bad or few):
                        continue
                    items.append(DiskPaths(
                        host=c.host, collected_at=c.collected_at,
                        evidence_age_hours=_age_hours(c.collected_at),
                        **{k: d[k] for k in ("disk", "vg", "driver", "paths", "enabled",
                                             "failed", "other", "optimised")}))
            return paged(PathsPage, items, "aix_path_health", args, limit, cursor, len(cols))
        return run(ctx, "aix_path_health", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_missing_checks(ctx: Context, host: str | None = None, limit: int = DEFAULT_LIMIT,
                           cursor: str | None = None) -> MissingPage:
        """Checks that did not answer (timeout, budget, refused) with the command to run
        by hand. Use it to say what is NOT known."""
        args = {"host": host, "limit": limit}

        def go():
            cols = ev.select(host)
            items = [MissingCheck(host=c.host, collected_at=c.collected_at,
                                  evidence_age_hours=_age_hours(c.collected_at),
                                  check=r["check"], status=r["status"], reason=r["reason"],
                                  command=r["command"])
                     for c in cols for r in c.get("C") if r["status"] in ("MISSING", "REFUSED")]
            return paged(MissingPage, items, "aix_missing_checks", args, limit, cursor, len(cols))
        return run(ctx, "aix_missing_checks", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_host_storage(ctx: Context, host: str,
                         sections: list[Section] | None = None) -> HostStorage:
        """Full storage evidence for one host. Ask only for the sections you need,
        e.g. ["disks","adapters"] or ["npiv_maps","vscsi_maps"] on a VIOS."""
        args = {"host": host, "sections": sections}

        def go():
            col = ev.host(host)
            data = to_dict(col)
            secs = {k: v for k, v in data.items() if k not in ("source", "header")}
            if sections:
                secs = {k: v for k, v in secs.items() if k in set(sections)}
            return HostStorage(host=col.host, collected_at=col.collected_at,
                               evidence_age_hours=_age_hours(col.collected_at),
                               header=data["header"], sections=secs)
        return run(ctx, "aix_host_storage", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_perf_summary(ctx: Context, host: str, days: int = 7, limit: int = DEFAULT_LIMIT,
                         cursor: str | None = None) -> PerfPage:
        """Daily performance summary for one host from its 5-minute history: CPU busy,
        physc against entitlement and virtual CPUs, run queue, memory, paging space and
        the busiest disks (avg, p95, max per day). Oldest day first."""
        args = {"host": host, "days": days, "limit": limit}

        def go():
            items = [PerfDaySummary(**d) for d in ev.perf_days(host, days)[host]]
            return paged(PerfPage, items, "aix_perf_summary", args, limit, cursor, 1)
        return run(ctx, "aix_perf_summary", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_perf_top(ctx: Context, metric: PerfRankMetric = "physc_p95", days: int = 7,
                     limit: int = 10, cursor: str | None = None) -> PerfRankPage:
        """Rank every host by one performance metric over the last `days` days (each
        host's worst day), highest first. E.g. physc_p95 for CPU-hungry LPARs,
        pct_time_over_entitlement for LPARs living on borrowed capacity,
        pgsp_used_max for memory pressure."""
        args = {"metric": metric, "days": days, "limit": limit}
        names = {"physc": "physc", "cpu_busy": "cpu_busy_pct", "runq": "runq",
                 "mem_comp": "mem_comp_pct", "pgsp_used": "pgsp_used_pct",
                 "pgsp_pageout": "pgsp_pageout_per_s"}

        def value(d: dict[str, Any]) -> float | None:
            if metric == "pct_time_over_entitlement":
                return d.get("pct_time_over_entitlement")
            if metric == "disk_busy_p95":
                vals = [x["p95"] for x in d.get("busiest_disks", []) if x.get("p95") is not None]
                return max(vals) if vals else None
            name, stat = metric.rsplit("_", 1)
            return (d.get(names[name]) or {}).get(stat)

        def go():
            per_host = ev.perf_days(None, days)
            items = []
            for h, ds in per_host.items():
                scored = [(value(d), d) for d in ds]
                scored = [(v, d) for v, d in scored if v is not None]
                if not scored:
                    continue
                v, d = max(scored, key=lambda x: x[0])
                items.append(PerfRank(host=h, value=v, date=d["date"], entitled=d["entitled"],
                                      virtual_cpus=d["virtual_cpus"], days_considered=len(ds)))
            items.sort(key=lambda r: (-r.value, r.host))
            return paged(PerfRankPage, items, "aix_perf_top", args, limit, cursor,
                         len(per_host), metric=metric)
        return run(ctx, "aix_perf_top", args, go)

    @mcp.tool(annotations=READ_ONLY)
    def aix_perf_findings(ctx: Context, host: str | None = None, days: int = 7,
                          min_severity: Severity = "low", limit: int = DEFAULT_LIMIT,
                          cursor: str | None = None) -> PerfFindingsPage:
        """Performance observations from the daily history: CPU at the virtual CPU
        ceiling, long periods over entitlement, run queue, paging space use and I/O,
        computational memory, busy disks. Whole estate when host is omitted."""
        args = {"host": host, "days": days, "min_severity": min_severity, "limit": limit}

        def go():
            floor = SEVERITY_ORDER[min_severity]
            per_host = ev.perf_days(host, days)
            items = [PerfFinding(**f) for ds in per_host.values() for d in ds
                     for f in perf_findings(d) if SEVERITY_ORDER[f["severity"]] >= floor]
            items.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.host, f.summary))
            return paged(PerfFindingsPage, items, "aix_perf_findings", args, limit, cursor,
                         len(per_host))
        return run(ctx, "aix_perf_findings", args, go)

    @mcp.resource("aix-mcp://about")
    def about() -> str:
        """What this server is and what it will never do."""
        return (f"aix-mcp {__version__}: read-only AIX guest-OS evidence server. "
                f"No command execution tools. Evidence directory: {ev.directory}")

    return mcp


def main_serve(evidence_dir: str | None = None) -> None:
    directory = evidence_dir or os.environ.get("AIX_MCP_EVIDENCE_DIR") or "./evidence"
    build_server(directory).run(transport="stdio")
