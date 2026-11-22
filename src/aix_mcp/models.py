"""Typed tool outputs. Every tool publishes an outputSchema built from these models,
so code-generating clients get exact field names and types.

Bump SCHEMA_VERSION when a field is renamed or removed (adding a field is not a bump).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1"

Severity = Literal["info", "low", "medium", "high"]
Section = Literal[
    "checks", "mounts", "filesystems", "exports", "disks", "paths", "target_ports",
    "adapters", "fc_links", "npiv_maps", "vscsi_maps", "npiv_ports", "notes",
]


class Evidenced(BaseModel):
    host: str
    collected_at: str = Field(description="UTC time the collector ran, YYYYMMDDTHHMMSSZ")
    evidence_age_hours: float | None = Field(
        description="Hours between collection and this answer. Say it when you answer.")


class LparIdentity(BaseModel):
    schema_version: str = SCHEMA_VERSION
    host: str
    role: str = Field(description="LPAR or VIOS")
    partition_id: int | None = Field(description="From uname -L; HMC LPAR id")
    partition_name: str | None
    machine_type_model: str | None = Field(description="e.g. 9105-42A; HMC managed system MTM")
    machine_serial: str | None = Field(description="HMC managed system serial")
    oslevel: str | None
    ioslevel: str | None = Field(description="VIOS level, VIOS only")


class HostInfo(Evidenced):
    role: str
    partition_id: int | None
    partition_name: str | None
    machine_type_model: str | None
    machine_serial: str | None
    oslevel: str | None
    ioslevel: str | None
    multipath: str | None = Field(description="Drivers detected, e.g. 'AIX-PCM PowerPath'")
    checks: str | None = Field(description="total=N ok=N missing=N na=N")


class Finding(Evidenced):
    id: str = Field(description="Stable finding type, e.g. path_not_enabled, too_few_paths")
    severity: Severity
    subject: str = Field(description="Disk, adapter, mount point or check the finding is about")
    summary: str
    evidence: dict[str, Any] = Field(description="Record fields the finding is based on")


class DiskPaths(Evidenced):
    disk: str
    vg: str | None
    driver: str | None = Field(description="AIX PCM, SDDPCM, PowerPath pseudo, non-MPIO, ...")
    paths: int | None
    enabled: int | None
    failed: int | None
    other: int | None = Field(description="Paths neither Enabled nor Failed (Missing, Defined, ...)")
    optimised: int | None = Field(description="ALUA optimised paths (lsmpio), AIX PCM only")


class MissingCheck(Evidenced):
    check: str
    status: Literal["MISSING", "REFUSED"]
    reason: str | None
    command: str | None = Field(description="Run this by hand if the data is needed")


class Page(BaseModel):
    schema_version: str = SCHEMA_VERSION
    total: int = Field(description="Matching items before paging")
    returned: int
    next_cursor: str | None = Field(
        description="Pass back as cursor, with the same other arguments, for the next page")
    hosts_considered: int
    note: str | None = Field(default=None, description="Hint, e.g. how to narrow a big result")


class HostsPage(Page):
    items: list[HostInfo]


class FindingsPage(Page):
    items: list[Finding]


class PathsPage(Page):
    items: list[DiskPaths]


class MissingPage(Page):
    items: list[MissingCheck]


class Stat(BaseModel):
    avg: float | None
    p95: float | None
    max: float | None


class DiskBusy(Stat):
    disk: str


class PerfDaySummary(BaseModel):
    host: str
    date: str = Field(description="YYYY-MM-DD (host local time of the recording)")
    interval_s: int | None = Field(description="Seconds between snapshots, 300 by default")
    snapshots: int
    cpu_busy_pct: Stat | None = Field(description="100 - idle, logical CPU view")
    cpu_wait_pct: Stat | None
    physc: Stat | None = Field(description="Physical processors consumed")
    entitled: float | None = Field(description="Entitled capacity (EC)")
    virtual_cpus: float | None
    logical_cpus: float | None
    pct_time_over_entitlement: float | None = Field(
        description="Share of snapshots with physc above EC (uncapped borrowing)")
    physc_peak_hour: str | None = Field(description="Hour (HH) with the highest average physc")
    runq: Stat | None
    memory_mb: int | None
    mem_comp_pct: Stat | None = Field(description="Computational memory %")
    pgsp_used_pct: Stat | None = Field(description="Paging space used %")
    pgsp_pageout_per_s: Stat | None
    busiest_disks: list[DiskBusy] = Field(description="Top disks by %busy p95")


class PerfPage(Page):
    items: list[PerfDaySummary]


PerfRankMetric = Literal[
    "physc_p95", "physc_max", "cpu_busy_p95", "pct_time_over_entitlement", "runq_p95",
    "mem_comp_max", "pgsp_used_max", "pgsp_pageout_p95", "disk_busy_p95",
]


class PerfRank(BaseModel):
    host: str
    value: float
    date: str = Field(description="Day the value was reached")
    entitled: float | None
    virtual_cpus: float | None
    days_considered: int


class PerfRankPage(Page):
    metric: str
    items: list[PerfRank]


class PerfFinding(BaseModel):
    host: str
    id: str = Field(description="perf_vcpu_ceiling, perf_over_entitlement, perf_low_utilisation, "
                                "perf_run_queue, perf_paging_space_io, perf_paging_space_used, "
                                "perf_computational_memory, perf_disk_busy")
    severity: Severity
    subject: str
    summary: str
    evidence: dict[str, Any]


class PerfFindingsPage(Page):
    items: list[PerfFinding]


class HostStorage(Evidenced):
    schema_version: str = SCHEMA_VERSION
    header: dict[str, str]
    sections: dict[str, list[dict[str, Any]]] = Field(
        description="Record lists by section name; layout in collectors/aix_storage_paths.ksh")
