"""Parse the pipe-delimited ``.kh`` record files written by the collectors.

One line is one record: ``TYPE|field|field|...``. A ``|`` inside a field was
turned into ``/`` by the collector, so splitting on ``|`` is safe. The layout of
each record type is documented at the end of ``collectors/aix_storage_paths.ksh``
and mirrored in :data:`LAYOUT`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAYOUT: dict[str, tuple[str, ...]] = {
    "H": ("key", "value"),
    "C": ("check", "status", "secs", "rc", "reason", "command"),
    "M": ("mountpoint", "device", "vfs", "class", "node", "action"),
    "F": ("mountpoint", "size_mb", "free_mb", "used_pct", "class"),
    "X": ("export", "fs_mountpoint", "fs_class", "action", "options"),
    "D": (
        "disk", "status", "location", "vg", "pvid", "size_mb", "pcm", "algorithm",
        "reserve", "queue_depth", "hcheck", "paths", "enabled", "failed", "other",
        "optimised", "driver", "description",
    ),
    "P": ("disk", "parent", "connection", "path_status", "status"),
    "T": (
        "fscsi", "adapter_wwpn", "link", "remote_port", "enabled", "disabled",
        "failed", "missing", "port_id",
    ),
    "A": (
        "adapter", "status", "location", "kind", "wwpn", "fscsi", "fc_err_recov",
        "dyntrk", "description",
    ),
    "L": ("fcs", "speed", "port_type", "attention"),
    "N": (
        "vfchost", "physloc", "client_id", "client_name", "client_os", "status", "fc",
        "fc_physloc", "ports", "flags", "vfc_client", "vfc_drc",
    ),
    "V": ("vhost", "physloc", "client_id", "vtd", "status", "lun", "backing", "backing_physloc"),
    "Q": ("fcs", "physloc", "fabric", "tports", "aports", "swwpns", "awwpns"),
    "O": ("subject", "note"),
}

# Fields that hold whole numbers. "-" or an empty field becomes None.
INT_FIELDS = {
    "size_mb", "free_mb", "used_pct", "queue_depth", "hcheck", "paths", "enabled",
    "failed", "other", "optimised", "disabled", "missing", "tports", "aports",
    "swwpns", "awwpns", "rc",
}
FLOAT_FIELDS = {"secs"}

RECORD_NAMES = {
    "H": "header", "C": "checks", "M": "mounts", "F": "filesystems", "X": "exports",
    "D": "disks", "P": "paths", "T": "target_ports", "A": "adapters", "L": "fc_links",
    "N": "npiv_maps", "V": "vscsi_maps", "Q": "npiv_ports", "O": "notes",
}

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _value(name: str, raw: str) -> Any:
    if raw in ("", "-"):
        return None
    if name in INT_FIELDS and _INT_RE.match(raw):
        return int(raw)
    if name in FLOAT_FIELDS and _FLOAT_RE.match(raw):
        return float(raw)
    return raw


def parse_line(line: str) -> tuple[str, dict[str, Any]] | None:
    """Return ``(type, fields)`` for one record line, or None for blank or unknown lines."""
    line = line.rstrip("\r\n")
    if not line or "|" not in line:
        return None
    rtype, _, rest = line.partition("|")
    names = LAYOUT.get(rtype)
    if names is None:
        return None
    parts = rest.split("|")
    if len(parts) > len(names):  # extra separators belong to the last (free text) field
        parts = parts[: len(names) - 1] + ["|".join(parts[len(names) - 1 :])]
    parts += [""] * (len(names) - len(parts))
    return rtype, {n: _value(n, p) for n, p in zip(names, parts)}


@dataclass
class Collection:
    """One collector run on one host."""

    source: str
    header: dict[str, str] = field(default_factory=dict)
    records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def host(self) -> str:
        return self.header.get("host") or "unknown"

    @property
    def role(self) -> str:
        return self.header.get("role") or "unknown"

    @property
    def collected_at(self) -> str:
        return self.header.get("collected_at") or ""

    def get(self, rtype: str) -> list[dict[str, Any]]:
        return self.records.get(rtype, [])

    def identity(self) -> dict[str, Any]:
        """LPAR identity, the key that joins guest-OS data to HMC-level data.

        ``uname -L`` gives "<partition id> <partition name>"; ``lsattr -El sys0``
        gives the machine type-model and serial. Together they match an HMC's
        managed-system MTMS and partition id.
        """
        lpar = (self.header.get("lpar") or "").split(None, 1)
        model_serial = (self.header.get("model_serial") or "").split()
        part_id = int(lpar[0]) if lpar and lpar[0].lstrip("-").isdigit() else None
        return {
            "host": self.host,
            "role": self.role,
            "partition_id": part_id,
            "partition_name": lpar[1] if len(lpar) > 1 else None,
            "machine_type_model": model_serial[0].removeprefix("IBM,") if model_serial else None,
            "machine_serial": model_serial[1].removeprefix("IBM,") if len(model_serial) > 1 else None,
            "oslevel": self.header.get("oslevel"),
            "ioslevel": self.header.get("ioslevel"),
        }


def parse_text(text: str, source: str = "<text>") -> Collection:
    col = Collection(source=source)
    for line in text.splitlines():
        parsed = parse_line(line)
        if parsed is None:
            continue
        rtype, rec = parsed
        if rtype == "H":
            col.header[str(rec["key"])] = "" if rec["value"] is None else str(rec["value"])
        else:
            col.records.setdefault(rtype, []).append(rec)
    return col


def parse_file(path: str | Path) -> Collection:
    p = Path(path)
    return parse_text(p.read_text(encoding="utf-8", errors="replace"), source=p.name)


def load_dir(directory: str | Path) -> dict[str, Collection]:
    """Load every ``*.kh`` file under ``directory`` and keep the newest run per host."""
    latest: dict[str, Collection] = {}
    for p in sorted(Path(directory).rglob("*.kh")):
        if not p.is_file():
            continue
        col = parse_file(p)
        old = latest.get(col.host)
        if old is None or col.collected_at > old.collected_at:
            latest[col.host] = col
    return latest


def to_dict(col: Collection) -> dict[str, Any]:
    out: dict[str, Any] = {"source": col.source, "header": dict(col.header)}
    for rtype, recs in col.records.items():
        out[RECORD_NAMES.get(rtype, rtype)] = recs
    return out
