"""Parse nmon-format CSV and summarise it per day.

Two sources produce the same format:
* ``topasout -a`` on the AIX persistent local recording (``/var/perf/daily/<host>_YYMMDD.topas``,
  written every 5 minutes by topasrec from the ``xmdaily`` inittab entry on a default install);
* nmon recordings (``nmon -f`` / ``topas_nmon``), usually run from cron.

Lines are ``SECTION,Tnnnn,v1,v2,...`` with one header line per section
(``SECTION,<title>,col1,col2,...``) and ``ZZZZ,Tnnnn,HH:MM:SS,DD-Mon-YYYY`` giving the time of
each snapshot. The file is not sorted, so nothing here relies on line order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# metric name -> (section, column)
METRICS: dict[str, tuple[str, str]] = {
    "cpu_user_pct": ("CPU_ALL", "User%"),
    "cpu_sys_pct": ("CPU_ALL", "Sys%"),
    "cpu_wait_pct": ("CPU_ALL", "Wait%"),
    "cpu_idle_pct": ("CPU_ALL", "Idle%"),
    "physc": ("LPAR", "PhysicalCPU"),
    "entitled": ("LPAR", "entitled"),
    "vcpus": ("LPAR", "VirtualCPUs"),
    "logical_cpus": ("LPAR", "LogicalCPUs"),
    "pool_idle": ("LPAR", "poolIdle"),
    "mem_pages_4k": ("MEMREAL", "Size 4k pages"),
    "mem_free_4k": ("MEMREAL", "free frames 4k"),
    "mem_comp_pct": ("MEMREAL", "%comp"),
    "mem_noncomp_pct": ("MEMREAL", "%noncomp"),
    "pgsp_used_pct": ("MEMVIRT", "%used"),
    "pgsp_pagein": ("MEMVIRT", "pgspgin"),
    "pgsp_pageout": ("MEMVIRT", "pgspgout"),
    "runq": ("PROC", "Runnable"),
}


@dataclass
class PerfDay:
    host: str
    date: str                     # YYYY-MM-DD from the first snapshot
    interval_s: int | None
    snapshots: int
    series: dict[str, list[float]] = field(default_factory=dict)       # metric -> values
    disk_busy: dict[str, list[float]] = field(default_factory=dict)    # hdisk -> %busy values
    times: list[str] = field(default_factory=list)                     # HH:MM per snapshot


_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _num(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse_nmon(text: str, host_hint: str = "") -> PerfDay:
    headers: dict[str, list[str]] = {}
    rows: dict[str, dict[str, list[str]]] = {}
    zzzz: dict[str, tuple[str, str]] = {}
    aaa: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.rstrip("\r\n").rstrip(",").split(",")
        if len(parts) < 2:
            continue
        sec, key = parts[0], parts[1]
        if sec == "AAA":
            aaa[key] = parts[2] if len(parts) > 2 else ""
        elif sec == "ZZZZ" and len(parts) >= 4:
            zzzz[key] = (parts[2], parts[3])
        elif key.startswith("T") and key[1:].isdigit():
            rows.setdefault(sec, {})[key] = parts[2:]
        else:
            headers[sec] = parts[2:]

    order = sorted(zzzz, key=lambda t: int(t[1:]))
    day = PerfDay(host=aaa.get("host") or host_hint, date="", snapshots=len(order),
                  interval_s=int(_num(aaa.get("interval", "")) or 0) or None)
    if order:
        d = zzzz[order[0]][1]  # DD-Mon-YYYY
        try:
            dd, mon, yyyy = d.split("-")
            day.date = f"{int(yyyy):04d}-{_MONTHS[mon[:3].title()]:02d}-{int(dd):02d}"
        except (ValueError, KeyError):
            day.date = d
    day.times = [zzzz[t][0][:5] for t in order]

    def column(sec: str, col: str) -> list[float] | None:
        hdr = headers.get(sec)
        if not hdr:
            return None
        names = [h.strip() for h in hdr]
        if col not in names:
            return None
        i = names.index(col)
        out = []
        for t in order:
            r = rows.get(sec, {}).get(t)
            v = _num(r[i]) if r is not None and i < len(r) else None
            out.append(v if v is not None else math.nan)
        return out

    for metric, (sec, col) in METRICS.items():
        vals = column(sec, col)
        if vals is not None:
            day.series[metric] = vals
    if "DISKBUSY" in headers:
        for name in (h.strip() for h in headers["DISKBUSY"]):
            if name.startswith("hdisk"):
                day.disk_busy[name] = column("DISKBUSY", name) or []
    if "cpu_idle_pct" in day.series:
        day.series["cpu_busy_pct"] = [100 - v for v in day.series["cpu_idle_pct"]]
    return day


def parse_nmon_file(path: str | Path, host_hint: str = "") -> PerfDay:
    return parse_nmon(Path(path).read_text(encoding="utf-8", errors="replace"), host_hint)


def _clean(vals: list[float]) -> list[float]:
    return [v for v in vals if not math.isnan(v)]


def pct(vals: list[float], p: float) -> float | None:
    v = sorted(_clean(vals))
    if not v:
        return None
    k = (len(v) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 2)


def stats(vals: list[float]) -> dict[str, float | None]:
    v = _clean(vals)
    if not v:
        return {"avg": None, "p95": None, "max": None}
    return {"avg": round(sum(v) / len(v), 2), "p95": pct(v, 95), "max": round(max(v), 2)}


def summarise(day: PerfDay, top_disks: int = 3) -> dict[str, Any]:
    s = {m: stats(v) for m, v in day.series.items()}
    ent = s.get("entitled", {}).get("max")
    vcpu = s.get("vcpus", {}).get("max")
    physc = day.series.get("physc", [])
    over_ent = (round(100 * sum(1 for v in _clean(physc) if ent and v > ent) / len(_clean(physc)), 1)
                if ent and _clean(physc) else None)
    peak_hour = None
    if physc and day.times:
        by_hour: dict[str, list[float]] = {}
        for t, v in zip(day.times, physc):
            if not math.isnan(v):
                by_hour.setdefault(t[:2], []).append(v)
        if by_hour:
            peak_hour = max(by_hour, key=lambda h: sum(by_hour[h]) / len(by_hour[h]))
    disks = sorted(((d, stats(v)) for d, v in day.disk_busy.items()),
                   key=lambda x: -(x[1]["p95"] or 0))[:top_disks]
    mem_mb = None
    if day.series.get("mem_pages_4k"):
        mem_mb = round((stats(day.series["mem_pages_4k"])["max"] or 0) * 4 / 1024)
    return {
        "host": day.host,
        "date": day.date,
        "interval_s": day.interval_s,
        "snapshots": day.snapshots,
        "cpu_busy_pct": s.get("cpu_busy_pct"),
        "cpu_wait_pct": s.get("cpu_wait_pct"),
        "physc": s.get("physc"),
        "entitled": ent,
        "virtual_cpus": vcpu,
        "logical_cpus": s.get("logical_cpus", {}).get("max"),
        "pct_time_over_entitlement": over_ent,
        "physc_peak_hour": peak_hour,
        "runq": s.get("runq"),
        "memory_mb": mem_mb,
        "mem_comp_pct": s.get("mem_comp_pct"),
        "pgsp_used_pct": s.get("pgsp_used_pct"),
        "pgsp_pageout_per_s": s.get("pgsp_pageout"),
        "busiest_disks": [{"disk": d, **st} for d, st in disks],
    }


def perf_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Observations from one day's summary. Thresholds are deliberately conservative."""
    out = []
    h, d = summary["host"], summary["date"]

    def add(fid, sev, subject, text, ev):
        out.append({"host": h, "id": fid, "severity": sev, "subject": subject,
                    "summary": f"{d}: {text}", "evidence": ev})

    physc, ent, vcpu = summary.get("physc") or {}, summary.get("entitled"), summary.get("virtual_cpus")
    if physc.get("p95") is not None and vcpu and physc["p95"] >= 0.9 * vcpu:
        add("perf_vcpu_ceiling", "medium", "cpu",
            f"physc p95 {physc['p95']} is at the virtual CPU ceiling ({vcpu} VPs)",
            {"physc": physc, "virtual_cpus": vcpu})
    over = summary.get("pct_time_over_entitlement")
    if over is not None and over >= 50:
        add("perf_over_entitlement", "low", "cpu",
            f"above entitlement {ent} for {over}% of the day (uncapped borrowing)",
            {"physc": physc, "entitled": ent})
    if physc.get("p95") is not None and ent and physc["p95"] < 0.2 * ent and ent >= 1:
        add("perf_low_utilisation", "info", "cpu",
            f"physc p95 {physc['p95']} is under 20% of entitlement {ent}",
            {"physc": physc, "entitled": ent})
    runq, lcpu = summary.get("runq") or {}, summary.get("logical_cpus")
    if runq.get("p95") is not None and lcpu and runq["p95"] > 2 * lcpu:
        add("perf_run_queue", "medium", "cpu",
            f"run queue p95 {runq['p95']} is over twice the {lcpu} logical CPUs",
            {"runq": runq, "logical_cpus": lcpu})
    po =summary.get("pgsp_pageout_per_s") or {}
    if po.get("p95") and po["p95"] > 10:
        add("perf_paging_space_io", "medium", "memory",
            f"paging space page-outs p95 {po['p95']}/s", {"pgsp_pageout_per_s": po})
    comp = summary.get("mem_comp_pct") or {}
    if comp.get("max") is not None and comp["max"] >= 90:
        add("perf_computational_memory", "medium", "memory",
            f"computational memory reached {comp['max']}%", {"mem_comp_pct": comp})
    pgsp = summary.get("pgsp_used_pct") or {}
    if pgsp.get("max") is not None and pgsp["max"] >= 50:
        add("perf_paging_space_used", "medium" if pgsp["max"] < 80 else "high", "memory",
            f"paging space {pgsp['max']}% used", {"pgsp_used_pct": pgsp})
    for dk in summary.get("busiest_disks", []):
        if dk.get("p95") is not None and dk["p95"] >= 70:
            add("perf_disk_busy", "medium", dk["disk"], f"{dk['disk']} %busy p95 {dk['p95']}",
                {"disk_busy": dk})
    return out
