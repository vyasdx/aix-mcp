import sys
from pathlib import Path

import pytest

from aix_mcp.collect import SshConfig, collect, read_targets, ssh_verb

FAKE = [sys.executable, str(Path(__file__).parent / "fake_ssh.py")]


def test_collect_writes_evidence(tmp_path):
    cfg = SshConfig(ssh=FAKE, verb_timeout=30)
    res = collect(cfg, ["host-01.example", "down.example"], tmp_path, parallel=2)
    ok, down = res
    assert ok["host"] == "host-01"
    assert ok["storage"] == "host-01_storage_20261120T101500Z.kh"
    assert ok["perf_days"] == ["261120"]
    assert ok["errors"] == ["perf day 261119: rc=2 aixmcp-dispatch: topasout could not convert"]
    assert (tmp_path / "host-01" / "host-01_storage_20261120T101500Z.kh").is_file()
    assert (tmp_path / "host-01" / "perf" / "host-01_261120.nmon.csv").is_file()
    assert down["host"] is None and "rc=255" in down["errors"][0]
    assert (tmp_path / "last_collect.json").is_file()


def test_targets_cannot_be_ssh_options(tmp_path):
    with pytest.raises(ValueError):
        ssh_verb(SshConfig(ssh=FAKE), "-oProxyCommand=evil", "version")
    f = tmp_path / "hosts.txt"
    f.write_text("host-01  # comment\n\nhost-02\n")
    assert read_targets([str(f)]) == ["host-01", "host-02"]
    with pytest.raises(ValueError):
        read_targets(["-oProxyCommand=x"])
