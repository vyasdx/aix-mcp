---
name: aix-cluster-checks
description: Read-only L1/L2 status checks inside AIX for PowerHA SystemMirror clusters, IBM Storage Scale (GPFS / Spectrum Scale), NIM servers and clients, and WPARs. Use for "is the cluster healthy", resource group state or location, cluster manager state, CAA repository disk, unsynced cluster changes, GPFS node or disk state, quorum, long waiters, NIM client or resource state, failed network installs, and WPAR state. Gives the exact read-only commands, how to read their output, what is serious, and what must never be run.
---

# AIX clusters and services: PowerHA, Storage Scale, NIM, WPAR (read-only)

aix-mcp does not collect cluster state yet. It does show shared and cluster mounts, shared-disk
reserve problems (`concurrent_vg_reserve`) and capacity. This skill gives a human the exact
**read-only** commands, then reads the output with them.

## Ground rules

1. Read-only, with **exact commands only**. These products have many commands that look like
   queries but change state, start heavy jobs, or run on every node. Never suggest anything that
   is not in a reference file below, and never pass free text through `clcmd` or `mmdsh`.
2. Cluster commands generally need root on a cluster node (Storage Scale: an admin node with
   working passwordless remote shell). Ask the admin to run them; do not ask for credentials.
3. A tool failing is not the cluster failing. `clstat`/`cldump` depend on SNMP and clinfo;
   `mmhealth` may not be available on AIX. Fall back to the core commands.
4. Transient states (joining, acquiring, arbitrating, recovering) are normal for minutes. Ask for a
   second sample before escalating, unless users are already affected.
5. Commands that fan out to all nodes can hang when a node is unreachable. One run, not a loop.

## Which reference

| Product | Use | Reference |
|---|---|---|
| PowerHA SystemMirror | Cluster manager state, resource groups, CAA and repository, sync state, logs | [references/powerha.md](references/powerha.md) |
| IBM Storage Scale (GPFS) | Node state and quorum, file systems and mounts, disks and NSDs, waiters, logs | [references/storage-scale.md](references/storage-scale.md) |
| NIM | Master daemon, client Cstate, SPOT and lpp_source state, network boot path, logs | [references/nim.md](references/nim.md) |
| WPAR | State of workload partitions in the global environment | [references/wpar.md](references/wpar.md) |

## First five minutes (any cluster ticket)

1. aix-mcp first: `aix_findings(host=<node>)` for `concurrent_vg_reserve`, `path_not_enabled`
   and `filesystem_used`. Shared disks that lost paths are a common root cause of cluster events.
2. Run the product's **minimum set** (top of each reference) on **one** node and read it here.
3. Decide: healthy / transient (re-check in 5 to 10 minutes) / escalate.
4. Escalate with the hand-off template from **aix-health-check**, adding: cluster or file system
   name, node states, resource group states and locations, and the last relevant log lines.

## Always page now

- PowerHA: a node in `RP_FAILED` or `ST_UNSTABLE`; a resource group in `ERROR` or `UNKNOWN`; a
  resource group that should be up is OFFLINE everywhere; the repository disk is not accessible.
- Storage Scale: quorum not achieved; a disk `down` or `unrecovered`; `mmhealth` FAILED for
  GPFS, FILESYSTEM or DISK; deadlock output; MMFS_FSSTRUCT, MMFS_SYSTEM_UNMOUNT or MMFS_DISKFAIL
  in the error log.
- NIM: only when a planned install window is blocked (nimesis down, SPOT not ready).
- WPAR: a production WPAR Broken.

## Never (summary; full lists in each reference)

PowerHA: any `clmgr` verb except `query`/`view` as listed, `clRGmove`, `clmgr sync`,
`clmgr verify` with FIX, `clmgr replace repository`, start/stop of cluster services, C-SPOC or
`smitty` cluster menus, the cluster test tool.
Storage Scale: `mmstartup`, `mmshutdown`, `mmchdisk`, `mmchconfig`, `mmmount`, `mmumount`,
`mmfsck` (any form, including `-n`), `mmfsadm`, `mmdsh`, `mmnsddiscover`, `mmcheckquota`,
mmhealth write forms.
NIM: any `nim -o` other than `showres`, `lslpp`, `fix_query`, `showlog`; any `nimclient -o`;
`nim -o check` and `nim -o lppchk` (they change state).
WPAR: `startwpar`, `stopwpar`, `rebootwpar`, `chwpar`, `rmwpar`, `mkwpar`, `syncwpar`, `clogin`.
