"""Turn collector records into findings.

A finding is an observation with evidence, not a verdict. Each one names the
record it came from, so a human can check the raw output on the host.
"""

from __future__ import annotations

from typing import Any

from .records import Collection

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}


def _f(col: Collection, fid: str, severity: str, subject: str, summary: str,
       evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": col.host,
        "id": fid,
        "severity": severity,
        "subject": subject,
        "summary": summary,
        "evidence": evidence,
        "collected_at": col.collected_at,
    }


def disk_findings(col: Collection, min_enabled_paths: int = 2) -> list[dict[str, Any]]:
    out = []
    for d in col.get("D"):
        name = d["disk"]
        total = d["paths"] or 0
        enabled = d["enabled"] or 0
        bad = (d["failed"] or 0) + (d["other"] or 0)
        ev = {k: d[k] for k in ("vg", "driver", "paths", "enabled", "failed", "other",
                                "optimised", "algorithm", "reserve", "hcheck")}
        if bad > 0:
            out.append(_f(col, "path_not_enabled", "high", name,
                          f"{bad} of {total} paths not Enabled ({d['failed'] or 0} Failed)", ev))
        if d["driver"] == "AIX PCM" and total > 0 and enabled < min_enabled_paths:
            out.append(_f(col, "too_few_paths", "medium", name,
                          f"{enabled} Enabled path(s); expected at least {min_enabled_paths}", ev))
        if d["driver"] == "AIX PCM" and d["hcheck"] == 0:
            out.append(_f(col, "hcheck_disabled", "low", name,
                          "hcheck_interval=0: failed paths are not health-checked back", ev))
        vg = d["vg"] or ""
        if "concurrent" in vg and d["reserve"] not in (None, "no_reserve"):
            out.append(_f(col, "concurrent_vg_reserve", "medium", name,
                          f"concurrent VG member with reserve_policy={d['reserve']}", ev))
        if d["status"] not in (None, "Available"):
            out.append(_f(col, "disk_not_available", "medium", name,
                          f"disk status {d['status']}", ev))
    return out


def adapter_findings(col: Collection) -> list[dict[str, Any]]:
    out = []
    for a in col.get("A"):
        if not str(a["adapter"]).startswith("fcs"):
            continue
        ev = {k: a[k] for k in ("kind", "fscsi", "fc_err_recov", "dyntrk", "status")}
        subj = a["fscsi"] or a["adapter"]
        if a["fc_err_recov"] not in (None, "fast_fail"):
            out.append(_f(col, "fc_err_recov", "low", subj,
                          f"fc_err_recov={a['fc_err_recov']} (fast_fail is usual with multipath)", ev))
        if a["dyntrk"] not in (None, "yes"):
            out.append(_f(col, "dyntrk", "low", subj,
                          f"dyntrk={a['dyntrk']} (yes lets paths survive N_Port ID changes)", ev))
    for t in col.get("T"):
        if t["link"] not in (None, "Up"):
            out.append(_f(col, "fc_link_not_up", "medium", t["fscsi"],
                          f"link {t['link']} to target port {t['remote_port']}", dict(t)))
    return out


def vios_findings(col: Collection) -> list[dict[str, Any]]:
    out = []
    for n in col.get("N"):
        if n["status"] != "LOGGED_IN":
            out.append(_f(col, "vfchost_not_logged_in", "medium", n["vfchost"],
                          f"client {n['client_id']} ({n['client_name']}) status {n['status']}",
                          dict(n)))
    for q in col.get("Q"):
        if q["fabric"] != "1":
            out.append(_f(col, "npiv_port_no_fabric", "low", q["fcs"],
                          "physical FC port reports no NPIV-capable fabric", dict(q)))
    return out


def capacity_findings(col: Collection, used_pct: int = 90) -> list[dict[str, Any]]:
    return [
        _f(col, "filesystem_used", "medium" if f["used_pct"] < 98 else "high", f["mountpoint"],
           f"{f['used_pct']}% used", dict(f))
        for f in col.get("F")
        if isinstance(f["used_pct"], int) and f["used_pct"] >= used_pct
    ]


def gap_findings(col: Collection) -> list[dict[str, Any]]:
    """Checks that did not answer. Missing data is reported, never guessed."""
    return [
        _f(col, "check_missing", "info", c["check"], c["reason"] or "no answer",
           {"command": c["command"], "secs": c["secs"]})
        for c in col.get("C")
        if c["status"] in ("MISSING", "REFUSED")
    ]


def all_findings(col: Collection, min_enabled_paths: int = 2,
                 used_pct: int = 90) -> list[dict[str, Any]]:
    out = (disk_findings(col, min_enabled_paths) + adapter_findings(col)
           + vios_findings(col) + capacity_findings(col, used_pct) + gap_findings(col))
    out.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], f["host"], f["subject"]))
    return out
