"""Command line: ``aix-mcp serve``, ``collect``, ``findings``, ``parse``, ``collectors``."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .bundled import copy_collectors, demo_dir
from .findings import all_findings
from .records import load_dir, parse_file, to_dict


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aix-mcp", description=__doc__)
    p.add_argument("--version", action="version", version=f"aix-mcp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the MCP server over stdio")
    s.add_argument("--evidence-dir", help="directory of *.kh files (or AIX_MCP_EVIDENCE_DIR)")
    s.add_argument("--demo", action="store_true",
                   help="serve the bundled synthetic evidence (no AIX needed)")

    pr = sub.add_parser("parse", help="print one .kh file as JSON")
    pr.add_argument("file")

    fi = sub.add_parser("findings", help="print findings for every host in a directory")
    fi.add_argument("directory", nargs="?")
    fi.add_argument("--demo", action="store_true", help="use the bundled synthetic evidence")
    fi.add_argument("--min-enabled-paths", type=int, default=2)

    co = sub.add_parser("collect", help="pull evidence from hosts over SSH (forced-command dispatcher)")
    co.add_argument("targets", nargs="+", help="host names/addresses, or files with one per line")
    co.add_argument("--evidence-dir", required=True)
    co.add_argument("--user", default="aixmcp")
    co.add_argument("--key", help="private key of the collection user")
    co.add_argument("--known-hosts", help="known_hosts file (host keys must already be in it)")
    co.add_argument("--port", type=int)
    co.add_argument("--parallel", type=int, default=16)
    co.add_argument("--timeout", type=int, default=180, help="seconds per request")
    co.add_argument("--quick", action="store_true", help="storage quick (no disk size, no fcstat)")
    co.add_argument("--perf-days", type=int, default=7, help="days of performance history (0: none)")
    co.add_argument("--no-storage", action="store_true")

    cl = sub.add_parser("collectors", help="copy the AIX-side scripts (collector, dispatch, installer)")
    cl.add_argument("dest", help="directory to copy them into")

    a = p.parse_args(argv)
    if a.cmd == "serve":
        from .server import main_serve  # imports the MCP SDK only when serving
        main_serve(str(demo_dir()) if a.demo else a.evidence_dir)
    elif a.cmd == "collect":
        from pathlib import Path

        from .collect import SshConfig, collect, read_targets
        cfg = SshConfig(user=a.user, key=a.key, known_hosts=a.known_hosts, port=a.port,
                        verb_timeout=a.timeout)
        results = collect(cfg, read_targets(a.targets), Path(a.evidence_dir), a.parallel,
                          a.quick, a.perf_days, not a.no_storage)
        for r in results:
            state = "ok" if not r["errors"] else "ERR"
            print(f"{state:3} {r['target']:<24} host={r['host'] or '-':<16} "
                  f"storage={r['storage'] or '-'} perf_days={len(r['perf_days'])} {r.get('secs', '-')}s")
            for e in r["errors"]:
                print(f"      {e}")
        return 0 if all(not r["errors"] for r in results) else 1
    elif a.cmd == "parse":
        json.dump(to_dict(parse_file(a.file)), sys.stdout, indent=2)
        print()
    elif a.cmd == "collectors":
        for f in copy_collectors(a.dest):
            print(f)
        print("Copy these to each AIX host; see docs/live-collection.md.", file=sys.stderr)
    elif a.cmd == "findings":
        if bool(a.demo) == bool(a.directory):
            p.error("findings: give a directory or --demo")
        directory = str(demo_dir()) if a.demo else a.directory
        out = [f for col in load_dir(directory).values()
               for f in all_findings(col, a.min_enabled_paths)]
        json.dump(out, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
