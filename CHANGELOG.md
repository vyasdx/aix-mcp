# Changelog

## Unreleased

- Six read-only skills (Agent Skills format) in `skills/`: `aix-health-check`,
  `aix-storage-paths`, `aix-vios-check`, `aix-performance-triage`, `aix-filesystem-full`,
  `aix-cluster-checks`. They guide L1/L2 checks and correlation with the aix-mcp tools, give
  exact read-only commands for areas the tools do not collect yet, and list what must never
  be run. `tests/test_skills.py` checks front matter, tool and finding names, and links.

## 0.2.0 (first PyPI release)

- On PyPI as `aix-mcp`, and listed in the official MCP registry as `io.github.vyasdx/aix-mcp`.
- `aix-mcp serve --demo` and `aix-mcp findings --demo` use bundled synthetic evidence, so the
  server can be tried without an AIX host.
- `aix-mcp collectors DIR` copies the AIX-side scripts (collector, dispatcher, installer) out of
  the installed package.
- Live collection over SSH:
  - `collectors/dispatch` is a forced-command entry point with the verbs `version`, `storage`,
    `storage quick`, `perf list` and `perf day YYMMDD`. Anything else is refused and logged to
    syslog.
  - `collectors/install_dispatch.ksh` creates a key-only non-root user, a `restrict` + `from=`
    key, and one exact sudo rule (checked by `visudo`). `-r` removes it all.
  - `aix-mcp collect` pulls in parallel with OpenSSH, using BatchMode and strict host keys. It
    fetches perf days incrementally and writes a run report.
- Performance history:
  - It reads the AIX persistent local recording (`/var/perf/daily`, converted with
    `topasout -a`) and nmon files.
  - New tools: `aix_perf_summary`, `aix_perf_top` and `aix_perf_findings`.
- Collector 0.2:
  - New `-k` option prints the records to stdout and keeps the last 10 runs.
  - The test hooks are ignored when the collector runs elevated.
  - It no longer inherits the caller's PATH.

## 0.1.0.dev0

- Tools are renamed with an `aix_` prefix: `aix_list_hosts`, `aix_findings`, `aix_path_health`,
  `aix_missing_checks`, `aix_lpar_identity`, `aix_host_storage`.
- Every tool has a typed output schema, `schema_version` and `evidence_age_hours`.
- `limit` (default 100, max 1000) and an opaque `next_cursor`. The cursor is bound to the query
  and the evidence snapshot.
- `aix_findings` gains a `finding_id` filter.
- One JSON audit line per call goes to stderr, and to the file set in `AIX_MCP_AUDIT_LOG`. It
  includes the W3C `traceparent` from the request's `_meta`.
- First public version: the storage, multipath, FC and VIOS collector, plus the evidence-mode MCP
  server.
