"""Command line: ``aix-mcp serve``, ``aix-mcp parse``, ``aix-mcp findings``."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .findings import all_findings
from .records import load_dir, parse_file, to_dict


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aix-mcp", description=__doc__)
    p.add_argument("--version", action="version", version=f"aix-mcp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the MCP server over stdio")
    s.add_argument("--evidence-dir", help="directory of *.kh files (or AIX_MCP_EVIDENCE_DIR)")

    pr = sub.add_parser("parse", help="print one .kh file as JSON")
    pr.add_argument("file")

    fi = sub.add_parser("findings", help="print findings for every host in a directory")
    fi.add_argument("directory")
    fi.add_argument("--min-enabled-paths", type=int, default=2)

    a = p.parse_args(argv)
    if a.cmd == "serve":
        from .server import main_serve  # imports the MCP SDK only when serving
        main_serve(a.evidence_dir)
    elif a.cmd == "parse":
        json.dump(to_dict(parse_file(a.file)), sys.stdout, indent=2)
        print()
    elif a.cmd == "findings":
        out = [f for col in load_dir(a.directory).values()
               for f in all_findings(col, a.min_enabled_paths)]
        json.dump(out, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
