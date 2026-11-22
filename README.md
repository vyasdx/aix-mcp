# aix-mcp

**A read-only [Model Context Protocol](https://modelcontextprotocol.io) server for the AIX guest OS.**
It lets an AI assistant answer questions such as *"which LPARs have a disk with fewer than two
working paths?"* or *"which NPIV client is not logged in on this VIOS?"* from evidence collected on
the hosts. It never changes anything.

> **Status: pre-alpha (0.1.0.dev0).** The collector has been run on AIX 7.3 TL4 and against
> synthetic VIOS, PowerPath and SDDPCM fixtures. Feedback from AIX and VIOS administrators is the
> most useful contribution right now. See [Contributing](#contributing).
>
> Not affiliated with, endorsed by or supported by IBM. AIX, PowerVM and IBM Power are trademarks
> of IBM Corp.

## Why a guest-OS layer

Management-level MCP servers for IBM Power, such as the ones that talk to an HMC or to PowerVS,
see the **frame**: managed systems, partitions, profiles, virtual adapters and serviceable events.
They do not see **inside** AIX: multipath state per disk, `hcheck_interval`, `fc_err_recov`, ALUA
optimised paths, filesystems, NFS mounts, or which checks hung.

`aix-mcp` covers that inside view. Every host record carries the LPAR identity (machine
type-model, serial and partition id), so an agent can join it with HMC-level data about the same
partition.

```
  AI assistant (any MCP client)
     |                      |
     | HMC / PowerVS MCP    | aix-mcp  (this project)
     v                      v
  frame, LPARs, VIOS      inside AIX: disks, paths, FC, mounts, VIOS mappings
  config, events          (joined on type-model + serial + partition id)
```

## Safety model

* **Read-only by construction.** No MCP tool runs a command. In v0.1 the server only reads
  collector output files. Every tool is annotated `readOnlyHint: true`.
* **Nothing installed on AIX.** The collector is one ksh93 script using base AIX commands. It needs
  no Python, no agent and no daemon on the host.
* **Allowlisted commands.** The collector refuses any command that is not on its list. The full
  list, with the reason for each command, is in [docs/commands.md](docs/commands.md).
* **Never stalls a host.** Every command runs under a watchdog. A slow, hung or stale command, for
  example `df` on a dead NFS mount, is killed or abandoned and recorded as `MISSING`. A whole-run
  budget caps the total time and the script runs at `nice 19`. On the test LPAR a full run took
  about 2.5 s and 0.2 s of CPU.
* **Never reads remote data.** NFS, CIFS and autofs client mounts are listed from the mount table
  only. They get no `df`, `ls` or `stat`. File contents are never read.
* **Missing is not healthy.** The server reports what it could not collect, and its instructions
  tell the model to say so.
* **The LLM is treated as untrusted input.** Tool arguments are validated, host names cannot
  become paths, and there is no free-form command tool. See [docs/design.md](docs/design.md).

## Quick start

```bash
pip install git+https://github.com/vyasdx/aix-mcp   # PyPI release is planned
aix-mcp findings tests/data                          # try it on the synthetic evidence
```

**1. Collect on a host** (as root; read-only):

```sh
/usr/bin/ksh93 aix_storage_paths.ksh -o /tmp/aixmcp_storage
```

This writes `<host>_storage_<UTC>.kh`, which holds the records, plus a `.raw/` directory with the
raw output of every command. Copy the `.kh` files to an evidence directory on your management
server with your usual tooling, for example scp or Ansible `fetch`.

**2. Serve them to an MCP client:**

```json
{
  "mcpServers": {
    "aix": {
      "command": "aix-mcp",
      "args": ["serve", "--evidence-dir", "/srv/aix-evidence"]
    }
  }
}
```

## Tools (v0.1)

| Tool | What it returns |
|---|---|
| `list_hosts` | Every host with evidence: role (LPAR or VIOS), AIX/VIOS level, LPAR identity, evidence age and check counts |
| `findings` | Storage and multipath findings with evidence, for one host or the whole estate, filtered by severity |
| `path_health` | Per-disk path counts (total, Enabled, Failed, other, ALUA-optimised) and the driver; problems only by default |
| `missing_checks` | Checks that did not answer, with the exact command to run by hand |
| `lpar_identity` | Partition id and name, machine type-model and serial, which form the join key to HMC data |
| `host_storage` | Full evidence for one host: disks, paths, adapters, FC links, mounts, filesystems, exports, NPIV and vSCSI maps, notes |

The estate-wide tools filter on the server, so asking about 1000 hosts returns only the rows that
matter.

## What the collector covers

* **Multipath:** AIX PCM (`lspath`, `lsmpio`, `lsmpio -ar`), PowerPath, SDDPCM, HDLM and Veritas
  DMP. It detects which drivers are present and runs only their query commands.
* **Disks:** the disk attributes that matter for paths: `algorithm`, `reserve_policy`,
  `queue_depth` and `hcheck_interval`.
* **FC adapters:** WWPN, `fc_err_recov`, `dyntrk`, link state and speed. It recognises NPIV
  virtual FC.
* **Filesystems:** mounts classified as local, cluster (GPFS), remote, pseudo or other. Capacity is
  read for local and cluster filesystems only.
* **NFS server:** exports mapped to the filesystem that holds them.
* **VIOS:** NPIV (`lsmap -npiv`, `lsnports`), vSCSI and SEA mappings through `ioscli`.

The record layout is documented at the end of
[collectors/aix_storage_paths.ksh](collectors/aix_storage_paths.ksh).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). In short:

* **v0.2:** live collection over SSH through a forced-command dispatcher. It uses a non-root user
  and an allowlist enforced on the host.
* **Next collectors:** VG capacity, `errpt` summary, paging and memory, and `lppchk`/`emgr`
  state.
* **Later:** streamable HTTP with authentication, and a release on PyPI with trusted publishing
  and attestations.

## Contributing

The best way to help is to **run the collector on a test LPAR or VIOS and open an issue** with
what looks wrong. Anonymised `.kh` output for unusual setups is welcome; it becomes a test fixture.
These setups are especially useful:

* PowerPath, HDLM or DMP;
* GPFS;
* NPIV with many clients;
* AIX 7.1 or 7.2.

Please replace host names, WWPNs and serials first; the issue template explains how. Never post
client data.

* Collector tests: `collectors/tests/run_fixtures.ksh` (needs ksh93 on AIX).
* Python tests: `pip install -e .[dev] && pytest`.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
