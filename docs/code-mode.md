# aix-mcp and "code mode" clients

Some MCP clients no longer call tools one at a time. Instead, the model writes a short program
against a typed API that is generated from the tools' schemas, and a sandbox runs it. Only the
final result goes back to the model. Cloudflare calls this Code Mode, and Anthropic describes the
same pattern as code execution with MCP.

Code mode is a **client-side** choice. MCP is still the contract for tools, schemas and
authentication. aix-mcp works with both kinds of client, and it is designed so that code mode
does not need to do the heavy lifting.

## Design choices

| Choice | Why it matters |
|---|---|
| A typed `outputSchema` on every tool | Generated code gets exact field names and types, so it does not have to guess at text. |
| `schema_version` in every answer | Scripts can detect a breaking change. |
| Estate-wide filters on the server (`aix_findings`, `aix_path_health` without `host`) | "Which of 1000 LPARs has a disk with fewer than 2 working paths?" is **one call** that returns only the matching rows. Neither a script nor the model has to loop over 1000 hosts. |
| `limit` + opaque `next_cursor` | Large results come back in pages. A cursor is bound to its query and to the evidence snapshot, so a stale cursor is refused instead of returning mixed data. |
| `evidence_age_hours` and `aix_missing_checks` | A script can't mistake old or missing data for healthy data. |
| A stable join key (`aix_lpar_identity`) | Lets a script join guest-OS data with HMC-level data on type-model, serial and partition id. |
| An `aix_` prefix on tool names | Avoids name clashes when one client loads several Power-related servers. |
| One audit line per call, with the W3C `traceparent` from `_meta` | One model action can become many calls, and the trace id ties them together in the audit log. |

## Security position

aix-mcp **does not run model-written code** and does not ship a sandbox. The server is the
security boundary: it is read-only, its arguments are validated, and it has no command tool. That
holds whoever the caller is.

If an organisation chooses a code-mode client, that client's sandbox is a separate component.
The organisation should approve it, keep it patched, and block its outbound network. Using it
adds no capability on AIX.
