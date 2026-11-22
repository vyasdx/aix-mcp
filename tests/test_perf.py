from pathlib import Path

from aix_mcp.perf import parse_nmon, parse_nmon_file, perf_findings, summarise

DATA = Path(__file__).parent / "data"
DAY = DATA / "host-01" / "perf" / "host-01_261120.nmon.csv"


def test_parse_file_and_times():
    day = parse_nmon_file(DAY)
    assert day.host == "host-01" and day.date == "2026-11-20"
    assert day.snapshots == 24 and day.interval_s == 300
    assert day.times[0] == "08:00" and day.times[-1] == "09:55"
    assert set(day.disk_busy) == {"hdisk0", "hdisk1"}  # cd0 is not an hdisk


def test_summary_numbers():
    s = summarise(parse_nmon_file(DAY))
    assert s["entitled"] == 0.5 and s["virtual_cpus"] == 2.0 and s["logical_cpus"] == 8.0
    assert s["physc"]["max"] == 1.95 and s["physc"]["p95"] == 1.95
    assert s["pct_time_over_entitlement"] == 75.0          # 18 of 24 snapshots
    assert s["memory_mb"] == 4096
    assert s["busiest_disks"][0]["disk"] == "hdisk1"
    assert s["physc_peak_hour"] == "09"


def test_findings_from_summary():
    ids = {f["id"] for f in perf_findings(summarise(parse_nmon_file(DAY)))}
    assert ids == {"perf_vcpu_ceiling", "perf_over_entitlement", "perf_run_queue",
                   "perf_paging_space_io", "perf_computational_memory",
                   "perf_paging_space_used", "perf_disk_busy"}


def test_missing_sections_are_tolerated():
    day = parse_nmon("AAA,host,h1,\nZZZZ,T0001,00:00:00,01-Jan-2026,\n")
    s = summarise(day)
    assert s["physc"] is None and s["busiest_disks"] == [] and perf_findings(s) == []
