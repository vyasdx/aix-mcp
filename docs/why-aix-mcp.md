# Why aix-mcp: value, viability, scale and AI readiness

aix-mcp lets an AI assistant answer questions about what is happening **inside** AIX LPARs and
VIOS (storage paths, NPIV, filesystems, performance history) **without ever getting a shell**.
It complements HMC-level tools such as IBM Power Autonomous Operations, which see the frame and
partitions but not the guest OS. Open source, Apache-2.0, not affiliated with IBM.

This page separates what has been **tested** from what is **designed but not yet proven**.
Demos and posts should use only the first column.

## 1. Valuable: the problem it solves

- AIX estates run critical workloads while experienced AIX admins are getting fewer. L1 teams
  often need root or an expert to answer basic questions ("is this disk redundant?", "why is
  this LPAR slow?").
- Giving an AI assistant SSH access is not acceptable to a security team. aix-mcp gives it a
  short list of **read-only questions** instead, with evidence and its age in every answer.
- **Skills** add an experienced admin's playbook: what to check first, how serious it is, who
  owns it, and what must never be run. They are written from IBM Redbooks and field practice.
- Typical uses: morning estate check, "server is slow" triage, path redundancy before VIOS or
  SAN maintenance, right-sizing from real history, L1 → L2 hand-off notes with evidence.

## 2. What is tested today

| Area | Evidence |
|---|---|
| MCP server | 9 read-only tools with typed output; paging; audit log per call. 43 automated tests, CI on Python 3.10, 3.12, 3.13 |
| Storage collector | Runs on real AIX 7.3 TL4: about 2.5 s and 0.2 s CPU per run; 53 of 53 fixture tests (PowerPath, SDDPCM and VIOS fixtures); a hung NFS mount is timed out and reported, never waited on |
| Live collection over SSH | On a real LPAR: first pull 5.2 s, incremental 3 s. Forced-command user, one exact sudo rule |
| Security tests (real LPAR) | Refused: command injection, unknown verbs, path tricks, option smuggling, interactive shells, port forwarding, `sudo` to anything else, a PATH hijack under sudo |
| Performance history | Reads AIX's own built-in 5-minute recording; no agent to install. About 290 KB per host per day after conversion |
| Skills | Six read-only skills; their commands checked on AIX 7.3 TL4. On first use they found two real issues on the lab LPAR: `/var` full (which had silently stopped performance recording) and time sync not configured |
| Demo mode | `aix-mcp serve --demo` with synthetic hosts; no AIX needed |

## 3. Designed, not yet proven (do not demo as working)

| Area | Status |
|---|---|
| VIOS live collection | Parser and fixtures done; never run on a real VIOS (no VIOS access yet) |
| PowerHA, Storage Scale, NIM checks | Skills give read-only commands from IBM documentation; not yet run on real clusters |
| Scale to hundreds of hosts | Parallel pull (up to 64 at once) and file-based evidence are built for it; tested on 1 real LPAR plus synthetic data |
| `pip install aix-mcp`, MCP registry | Release prepared; waiting for the first PyPI publish |
| End-to-end with an AI client using the skills | Planned test |
| Local or on-premises models | Should work (plain MCP); not yet tested |
| RBAC instead of sudo | Not yet tested |

## 4. Viable: why it can be adopted

- **Nothing to install inside the OS except two ksh scripts**: no agent, no daemon, no new
  ports. A key-only non-root user and one exact sudo rule. Remove with one command.
- **Security review friendly**: read-only by design, every command on a published allowlist,
  every call audited, the MCP server never holds an SSH key.
- **Model and vendor neutral**: standard MCP, so any MCP-capable assistant can use it.
- **Small adoption steps**: demo mode → one lab LPAR → a read-only pilot on a few hosts → a
  wider rollout through existing automation.
- **Open source** (Apache-2.0): free to evaluate and to use internally.

## 5. Scalable: how it is built for large estates

- Collection is out of band and parallel; the AI never waits on SSH.
- Evidence is plain files per host; the server reads files, so it stays fast and cannot
  disturb production hosts.
- Incremental performance pulls (only new days); paging cursors on every list.
- One finding format across hosts, so estate-wide questions ("which LPARs had disks on one path
  yesterday?") are a single call.

## 6. AI ready

- Model Context Protocol with typed output schemas and read-only annotations on every tool.
- Works with code-mode style agents (structured results, bound paging cursors, trace ids).
- Skills in the open Agent Skills format; next step is serving them over MCP's skills extension.
- Audit lines carry the caller's W3C trace id, so an agent run can be traced end to end.

## 7. What would move it forward

- Access to a VIOS and HMC lab, to finish and prove VIOS and NPIV correlation.
- Testers with PowerHA, Storage Scale or NIM environments.
- Feedback from AIX teams on which questions they would ask first.
