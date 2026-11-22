"""Live collection over SSH through the forced-command dispatcher (v0.2).

This runs as a scheduled job on the management tier (cron, AAP, or by hand), never as an
MCP tool: the MCP server keeps holding no keys and only reads the evidence directory.

For every host it asks the dispatcher for:
  version          -> host name used for the evidence folder
  storage [quick]  -> one .kh file
  perf list / perf day YYMMDD -> nmon-format CSV per day (only days not already stored,
                                 plus today, which is still growing)
OpenSSH does the transport, with BatchMode and strict host key checking, so it uses your
existing known_hosts and key management.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:_-]{0,252}$")  # never starts with '-'
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DAY_RE = re.compile(r"^\d{6}$")


@dataclass
class SshConfig:
    user: str = "aixmcp"
    key: str | None = None
    known_hosts: str | None = None
    ssh: str | list[str] = "ssh"
    connect_timeout: int = 10
    verb_timeout: int = 180
    port: int | None = None


def ssh_verb(cfg: SshConfig, target: str, verb: str) -> tuple[int, bytes, str]:
    if not _TARGET_RE.match(target):
        raise ValueError(f"bad target {target!r}")
    cmd = (list(cfg.ssh) if isinstance(cfg.ssh, list) else [cfg.ssh]) + ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", f"ConnectTimeout={cfg.connect_timeout}", "-o", "ServerAliveInterval=15",
           "-o", "ClearAllForwardings=yes", "-C", "-T"]
    if cfg.key:
        cmd += ["-i", cfg.key, "-o", "IdentitiesOnly=yes"]
    if cfg.known_hosts:
        cmd += ["-o", f"UserKnownHostsFile={cfg.known_hosts}"]
    if cfg.port:
        cmd += ["-p", str(cfg.port)]
    cmd += [f"{cfg.user}@{target}", verb]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=cfg.verb_timeout,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, b"", f"timeout after {cfg.verb_timeout}s"
    return p.returncode, p.stdout, p.stderr.decode(errors="replace").strip()[:300]


def collect_host(cfg: SshConfig, target: str, evidence: Path, quick: bool = False,
                 perf_days: int = 7, storage: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    res: dict[str, Any] = {"target": target, "host": None, "storage": None,
                           "perf_days": [], "errors": []}
    rc, out, err = ssh_verb(cfg, target, "version")
    if rc != 0:
        res["errors"].append(f"version: rc={rc} {err}")
        res["secs"] = round(time.monotonic() - t0, 1)
        return res
    info = dict(line.split(" ", 1) for line in out.decode(errors="replace").splitlines()
                if " " in line)
    host = info.get("host", "").strip()
    if not _NAME_RE.match(host):
        host = re.sub(r"[^A-Za-z0-9._-]", "_", target)[:64]
    res["host"] = host
    hdir = evidence / host
    hdir.mkdir(parents=True, exist_ok=True)

    if storage:
        rc, out, err = ssh_verb(cfg, target, "storage quick" if quick else "storage")
        text = out.decode(errors="replace")
        m = re.search(r"^H\|collected_at\|(\d{8}T\d{6}Z)$", text, re.M)
        if rc == 0 and m and "\nH|host|" in "\n" + text:
            f = hdir / f"{host}_storage_{m.group(1)}.kh"
            f.write_text(text, encoding="utf-8")
            res["storage"] = f.name
        else:
            res["errors"].append(f"storage: rc={rc} {err or 'no records'}")

    if perf_days > 0:
        rc, out, err = ssh_verb(cfg, target, "perf list")
        if rc != 0:
            res["errors"].append(f"perf list: rc={rc} {err}")
        else:
            days = sorted({ln.split("|")[0] for ln in out.decode().splitlines()
                           if _DAY_RE.match(ln.split("|")[0])})[-perf_days:]
            pdir = hdir / "perf"
            pdir.mkdir(exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%y%m%d")
            for d in days:
                f = pdir / f"{host}_{d}.nmon.csv"
                if f.exists() and d < today and d != days[-1]:
                    continue  # complete day already stored
                rc, out, err = ssh_verb(cfg, target, f"perf day {d}")
                if rc == 0 and b"ZZZZ," in out:
                    f.write_bytes(out)
                    res["perf_days"].append(d)
                else:
                    res["errors"].append(f"perf day {d}: rc={rc} {err}")
    res["secs"] = round(time.monotonic() - t0, 1)
    return res


def read_targets(items: list[str]) -> list[str]:
    out = []
    for it in items:
        p = Path(it)
        lines = p.read_text().splitlines() if p.is_file() else [it]
        for ln in lines:
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            if not _TARGET_RE.match(ln):
                raise ValueError(f"bad target {ln!r}")
            out.append(ln)
    return out


def collect(cfg: SshConfig, targets: list[str], evidence: Path, parallel: int = 16,
            quick: bool = False, perf_days: int = 7, storage: bool = True) -> list[dict[str, Any]]:
    evidence.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, min(parallel, 64))) as pool:
        results = list(pool.map(
            lambda t: collect_host(cfg, t, evidence, quick, perf_days, storage), targets))
    run = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "targets": len(targets), "ok": sum(1 for r in results if not r["errors"]),
           "results": results}
    (evidence / "last_collect.json").write_text(json.dumps(run, indent=2))
    return results
