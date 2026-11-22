# Changelog

## Unreleased (0.1.0.dev0)

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
