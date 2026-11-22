from pathlib import Path

import pytest

from aix_mcp.findings import all_findings
from aix_mcp.records import load_dir, parse_line, parse_text

DATA = Path(__file__).parent / "data"


def test_parse_line_types_and_padding():
    t, rec = parse_line("F|/data01|102400|3072|97|local")
    assert t == "F"
    assert rec == {"mountpoint": "/data01", "size_mb": 102400, "free_mb": 3072,
                   "used_pct": 97, "class": "local"}
    t, rec = parse_line("O|hdisk1")  # short line is padded
    assert rec == {"subject": "hdisk1", "note": None}
    assert parse_line("garbage") is None
    assert parse_line("Z|unknown|type") is None


def test_extra_separators_join_into_last_field():
    _, rec = parse_line("O|vios|a|b|c")
    assert rec["note"] == "a|b|c"


def test_load_dir_keeps_newest_per_host(tmp_path):
    old = "H|host|host-09\nH|collected_at|20260101T000000Z\nH|oslevel|old\n"
    new = "H|host|host-09\nH|collected_at|20260201T000000Z\nH|oslevel|new\n"
    (tmp_path / "a.kh").write_text(old)
    (tmp_path / "b.kh").write_text(new)
    hosts = load_dir(tmp_path)
    assert hosts["host-09"].header["oslevel"] == "new"


def test_identity_join_key():
    hosts = load_dir(DATA)
    ident = hosts["host-01"].identity()
    assert ident["partition_id"] == 5
    assert ident["partition_name"] == "host-01"
    assert ident["machine_type_model"] == "9105-42A"
    assert ident["machine_serial"] == "02SYN0001"


def test_findings_lpar():
    col = load_dir(DATA)["host-01"]
    ids = {(f["id"], f["subject"]) for f in all_findings(col)}
    assert ("path_not_enabled", "hdisk1") in ids
    assert ("too_few_paths", "hdisk2") in ids
    assert ("hcheck_disabled", "hdisk2") in ids
    assert ("concurrent_vg_reserve", "hdisk2") in ids
    assert ("fc_err_recov", "fscsi1") in ids
    assert ("dyntrk", "fscsi1") in ids
    assert ("fc_link_not_up", "fscsi1") in ids
    assert ("filesystem_used", "/data01") in ids
    assert ("check_missing", "size_hdisk2") in ids
    assert not any(s == "hdisk0" for _, s in ids)
    # highest severity first
    assert all_findings(col)[0]["severity"] == "high"


def test_findings_vios():
    col = load_dir(DATA)["vios-01"]
    ids = {(f["id"], f["subject"]) for f in all_findings(col)}
    assert ids == {("vfchost_not_logged_in", "vfchost2"), ("npiv_port_no_fabric", "fcs1")}


def test_remote_mounts_are_listed_not_measured():
    col = load_dir(DATA)["host-01"]
    remote = [m for m in col.get("M") if m["class"] == "remote"]
    assert remote and all(m["action"].startswith("not read") for m in remote)
    measured = {f["mountpoint"] for f in col.get("F")}
    assert not measured & {m["mountpoint"] for m in remote}


def test_parse_text_ignores_blank_and_crlf():
    col = parse_text("H|host|h1\r\n\r\nD|hdisk9|Available\r\n")
    assert col.host == "h1"
    assert col.get("D")[0]["disk"] == "hdisk9"


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", "x" * 70, "h;rm"])
def test_server_rejects_bad_host_names(bad):
    pytest.importorskip("mcp")
    from aix_mcp.server import Evidence
    with pytest.raises(ValueError):
        Evidence(DATA).host(bad)
