"""The bundled demo evidence and collectors work from an installed or source tree."""

import json
import os
import stat

from aix_mcp.bundled import COLLECTOR_FILES, demo_dir
from aix_mcp.cli import main


def test_findings_demo(capsys):
    assert main(["findings", "--demo"]) == 0
    found = json.loads(capsys.readouterr().out)
    hosts = {f["host"] for f in found}
    assert {"host-01", "vios-01"} <= hosts


def test_demo_dir_has_storage_and_perf():
    d = demo_dir()
    assert list(d.glob("*.kh"))
    assert list(d.glob("*/perf/*.nmon.csv"))


def test_collectors_copy(tmp_path, capsys):
    assert main(["collectors", str(tmp_path / "out")]) == 0
    for name in COLLECTOR_FILES:
        f = tmp_path / "out" / name
        assert f.is_file() and f.stat().st_size > 0
        if os.name != "nt":
            assert f.stat().st_mode & stat.S_IXUSR
