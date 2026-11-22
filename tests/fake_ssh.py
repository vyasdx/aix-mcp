"""Stand-in for `ssh user@host VERB` in tests: answers like collectors/dispatch would,
from tests/data. The verb is the last argument; the target is the one before it."""

import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
target, verb = sys.argv[-2].split("@", 1)[1], sys.argv[-1]
out = sys.stdout.buffer

if target == "down.example":
    sys.stderr.write("ssh: connect to host down.example port 22: Connection timed out\n")
    sys.exit(255)
if verb == "version":
    out.write(b"dispatch 0.2\nhost host-01\ncollector 0.2\n")
elif verb in ("storage", "storage quick"):
    out.write((DATA / "host-01_storage_20261120T101500Z.kh").read_bytes())
elif verb == "perf list":
    out.write(b"261119|100\n261120|2000\n")
elif verb == "perf day 261120":
    out.write((DATA / "host-01" / "perf" / "host-01_261120.nmon.csv").read_bytes())
elif verb == "perf day 261119":
    sys.stderr.write("aixmcp-dispatch: topasout could not convert\n")
    sys.exit(2)
else:
    sys.stderr.write("aixmcp-dispatch: unknown request\n")
    sys.exit(2)
