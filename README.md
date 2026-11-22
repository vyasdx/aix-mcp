<p align="center">
  <img src="https://raw.githubusercontent.com/vyasdx/aix-mcp/main/docs/assets/banner.svg" alt="aix-mcp: read-only MCP server for the AIX guest OS" width="100%">
</p>

<p align="center">
  <a href="https://github.com/vyasdx/aix-mcp/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/vyasdx/aix-mcp/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-2dd4bf"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-2dd4bf">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server-2dd4bf">
  <img alt="read-only" src="https://img.shields.io/badge/mode-read--only-22c55e">
  <img alt="status" src="https://img.shields.io/badge/status-pre--alpha-f59e0b">
</p>

<p align="center">
  <b>Ask your AI assistant what is happening <i>inside</i> your AIX LPARs and VIOS,<br>
  without giving it a shell.</b>
</p>

---

**aix-mcp** is an open-source [Model Context Protocol](https://modelcontextprotocol.io) server for
the AIX guest OS. It turns read-only evidence from your hosts into typed, filterable answers about:

* disks and multipath;
* FC and NPIV;
* VIOS mappings;
* filesystems.

Any MCP client can use it: an IDE assistant, a chat app or your own agent. It never changes
anything.

> Not affiliated with, endorsed by or supported by IBM. AIX, PowerVM and IBM Power are trademarks
> of IBM Corp.

## What it looks like

> **You:** Any storage problems across the estate I should know about before tonight's change?
>
> **Assistant** *(calls `aix_findings` with `min_severity: "medium"`)*: Two hosts have evidence, collected about 2 hours ago.
> On **host-01**:
> - **hdisk1** (datavg) has 1 of 2 paths Failed, so it is running on a single path.
> - **fscsi1** reports link **Down** to target port `500507680130aa02`, which is probably the same cause.
> - **/data01** is 97% full.
>
> On **vios-01**, **vfchost2** (client 7, host-07) is **NOT_LOGGED_IN**.
>
> One check, `bootinfo -s hdisk2`, did not answer in time, so hdisk2's size is unknown, not zero.

Under the hood, the agent gets compact typed JSON like this:

```json
{
  "schema_version": "1",
  "total": 2, "returned": 1, "hosts_considered": 2,
  "next_cursor": "eyJvIjogMSwgImsiOiAiOWU3MGNlZDJjODFiMmU0NCJ9",
  "items": [{
    "host": "host-01", "disk": "hdisk1", "vg": "datavg", "driver": "AIX PCM",
    "paths": 2, "enabled": 1, "failed": 1, "other": 0, "optimised": 1,
    "collected_at": "20261120T101500Z", "evidence_age_hours": 1.9
  }]
}
```

## Why a guest-OS layer

HMC-level and PowerVS-level MCP servers see the **frame**: managed systems, partitions, profiles,
virtual adapters and serviceable events. They don't see **inside** AIX:

* the state of each disk path;
* `hcheck_interval` and `fc_err_recov`;
* ALUA optimised paths;
* full filesystems;
* stale NFS mounts;
* which checks hung.

aix-mcp is that inside view. Every answer carries the **LPAR identity** (machine type-model,
serial and partition id), so an agent can join it with HMC-level data about the same partition.

```mermaid
flowchart LR
    C["AI assistant<br/>(any MCP client)"]
    H["HMC / PowerVS<br/>MCP servers"]
    A["<b>aix-mcp</b><br/>(management server)"]
    E[("evidence<br/>*.kh files")]
    L["AIX LPARs and VIOS<br/>ksh93 collector, base commands only"]
    C -- "frame, LPARs,<br/>events" --> H
    C -- "disks, paths, FC,<br/>mounts, VIOS maps" --> A
    A -- reads --> E
    L -- "scp / Ansible fetch" --> E
    H -. "join on MTM + serial<br/>+ partition id" .- A
```

## Safety model

| | |
|---|---|
| **Read-only by construction** | No tool runs a command. In v0.1 the server only reads collector files, and every tool is annotated `readOnlyHint`. |
| **Nothing installed on AIX** | One ksh93 script that uses base AIX commands. No Python, agent or daemon on the host. |
| **Allowlisted commands** | The collector refuses anything that is not on its list. The full list is in [docs/commands.md](docs/commands.md). |
| **Never stalls a host** | Each command runs under a watchdog, and a hung `df` on a dead NFS mount is abandoned and marked `MISSING`. A run budget caps the total time, and the script runs at `nice 19`. A lab run took about 2.5 s and 0.2 s of CPU. |
| **Never reads remote data** | NFS, CIFS and autofs client mounts are listed from the mount table only. File contents are never read. |
| **Missing is not healthy** | Gaps are reported with the command to run by hand. |
| **Auditable** | One JSON audit line per tool call. It carries the caller's W3C `traceparent` from `_meta`, so every call from one agent script can be tied together. |
| **The LLM is untrusted** | Arguments are validated, host names never become paths, and paging cursors are bound to their query. See [docs/design.md](docs/design.md). |

## Quick start

```bash
pip install git+https://github.com/vyasdx/aix-mcp      # PyPI release coming
aix-mcp findings tests/data                             # try it on synthetic evidence
```

**1. Collect on each host** (as root; read-only):

```sh
/usr/bin/ksh93 aix_storage_paths.ksh -o /tmp/aixmcp_storage
```

Copy the resulting `<host>_storage_<UTC>.kh` files to an evidence directory on your management
server. Use the tooling you already trust, for example `scp` or Ansible `fetch`.

**2. Point your MCP client at it** (see [examples/](examples/)):

```json
{
  "mcpServers": {
    "aix": {
      "command": "aix-mcp",
      "args": ["serve", "--evidence-dir", "/srv/aix-evidence"],
      "env": { "AIX_MCP_AUDIT_LOG": "/var/log/aix-mcp/audit.jsonl" }
    }
  }
}
```

## Tools

| Tool | Answers | Scope |
|---|---|---|
| `aix_list_hosts` | What do we have evidence for, how old is it, and what AIX/VIOS level is it? | estate |
| `aix_findings` | What is wrong, most severe first, with evidence. You can filter by severity or finding type. | host or estate |
| `aix_path_health` | Which disks have a failed path or too few paths, per driver and with ALUA counts? | host or estate |
| `aix_missing_checks` | What could we *not* collect, and the command to run by hand | host or estate |
| `aix_lpar_identity` | The machine type-model, serial and partition id, which form the join key to HMC data | host |
| `aix_host_storage` | Full evidence for one host, limited to the sections you ask for | host |

Every tool has a typed **output schema**, a `schema_version`, `evidence_age_hours`, a `limit`
(default 100, max 1000) and an opaque `next_cursor`. Estate-wide questions are filtered on the
server, so a question across 1000 LPARs returns only the rows that matter. This works with plain
tool-calling clients and with code-execution ("code mode") clients. See
[docs/code-mode.md](docs/code-mode.md).

## What the collector covers

* **Multipath:** AIX PCM (`lspath`, `lsmpio`, `lsmpio -ar`), PowerPath, SDDPCM, HDLM and Veritas
  DMP. It detects which drivers are present, then runs only their query commands.
* **Disks:** `algorithm`, `reserve_policy`, `queue_depth`, `hcheck_interval`, size, PVID and VG.
  It also flags concurrent VGs whose reserve policy is not `no_reserve`.
* **FC adapters:** WWPN, `fc_err_recov`, `dyntrk`, link state, speed and target ports. It
  recognises NPIV virtual FC.
* **Filesystems:** local, cluster (GPFS), remote, pseudo or other. Capacity is read for local
  and cluster filesystems only.
* **NFS server:** exports mapped to the filesystem that holds them.
* **VIOS:** NPIV (`lsmap -npiv`, `lsnports`), vSCSI and SEA mappings through `ioscli`.

The test suite covers synthetic VIOS, PowerPath and SDDPCM setups.

## Roadmap

* **v0.2:** live collection over SSH through a forced-command dispatcher. It uses a non-root user,
  and the allowlist is enforced on the host.
* **Next collectors:** VG capacity, an `errpt` summary, paging and memory, and `lppchk`/`emgr`
  state.
* **Later:** streamable HTTP with authentication, and a PyPI release with trusted publishing.

Details are in [docs/roadmap.md](docs/roadmap.md).

## Help wanted: AIX and VIOS admins

The most valuable contribution right now is **running the collector on a test LPAR or VIOS** and
[opening an issue](https://github.com/vyasdx/aix-mcp/issues/new/choose) about anything that looks
wrong. Anonymised output from these setups becomes test fixtures:

* PowerPath, HDLM or DMP;
* GPFS;
* busy NPIV VIOS;
* AIX 7.1 or 7.2.

Please never post client data. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
pip install -e ".[dev]" && pytest                # Python tests
ksh93 collectors/tests/run_fixtures.ksh          # collector fixture tests (on AIX)
```

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
