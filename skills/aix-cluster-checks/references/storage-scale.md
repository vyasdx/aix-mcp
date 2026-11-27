# IBM Storage Scale (GPFS): read-only checks

Sources: GC28-3197 Spectrum Scale 5.1.1 Command and Programming Reference (syntax), SG24-8254
and REDP-5254 (problem determination on AIX). Paraphrased. Commands live in `/usr/lpp/mmfs/bin`.
Most need root; cluster-wide queries also need working passwordless remote shell between nodes.
Add `-Y` for colon-separated output where supported.

## Minimum set (run on one node)

```sh
/usr/lpp/mmfs/bin/mmgetstate -a -L -s
/usr/lpp/mmfs/bin/mmlsmount all -L
/usr/lpp/mmfs/bin/mmlsdisk <fs> -e          # for each production file system
/usr/lpp/mmfs/bin/mmdiag --waiters          # on the node with the problem
tail -n 200 /var/adm/ras/mmfs.log.latest
```

## 1. Nodes and quorum: `mmgetstate -a -L -s`

| State | Meaning | Severity |
|---|---|---|
| `active` | Daemon ready | OK |
| `arbitrating` | Trying to form quorum | low if brief; **page now** if it persists or many nodes show it |
| `down` | Daemon not running or recovering | **page now** for a quorum node or a node serving file systems; low for a planned client |
| `unknown` | Node not reachable by the command | medium (check network/remote shell); high for a quorum node |
| `unresponsive` | Daemon running but not answering | **page now** |

Healthy: every expected node active, summary "Quorum achieved", active quorum nodes ≥ quorum
value. A `*` after the quorum number means tiebreaker disks are in use. Zero margin (active
quorum nodes = quorum value): **medium**, one more failure stops the cluster. `-a` silently
skips unreachable nodes; add `-v` for detail.

## 2. File systems: `mmlsmount all -L`, `mmlsfs <fs>`

`mmlsmount all -L`: each production file system mounted on the expected number of nodes.
"not mounted" for a production file system: **high**. `mmlsfs <fs>`: `--maintenance-mode No`;
replication (`-m`, `-r`) as designed.

## 3. Disks: `mmlsdisk <fs> -e` (main L1 check)

Healthy output: `6027-623 All disks up and ready`. Otherwise read status and availability:

| Availability | Severity | | Status | Severity |
|---|---|---|---|---|
| `up` | OK | | `ready` | OK |
| `recovering` | low (do not interfere) | | `suspended` | low (confirm planned) |
| `down` | **page now** | | `to be emptied`, `being emptied`, `emptied` | low (planned change?) |
| `unrecovered` | **page now** | | `replacing`, `replacement` | low (planned replacement) |

A stopped disk stays down until an admin starts it (a change). `mmlsdisk` does not work if GPFS
is down. `mmlsdisk <fs> -L` adds descriptor holders (`desc`) and quorum disk counts.
`mmlsnsd -X` maps NSDs to `hdiskN` and servers. Avoid `mmlsnsd -M` (slow, all nodes). For the
AIX side of a disk, use **aix-storage-paths**.

## 4. Health monitor (if available on your AIX level)

`mmhealth node show --unhealthy --nocolor`, `mmhealth cluster show --nocolor`,
`mmhealth node eventlog --day --nocolor`. States: HEALTHY ok; TIPS advisory (info); CHECKING
re-check later; DISABLED info unless unexpected; DEGRADED medium; FAILED **page now**; DEPEND
means a component it depends on failed, so look at that one first. Events like `gpfs_down`,
`quorum_down`, `stale_mount`, `fsstruct` need escalation. If mmhealth is not supported or not
running on the node, use sections 1 to 3.

## 5. Waiters and hangs: `mmdiag`

`mmdiag --waiters` (2 or 3 samples about 30 seconds apart), `mmdiag --deadlock`,
`mmdiag --network`, `mmdiag --memory`, `mmdiag --version`, `mmdiag --config`. Local node only;
needs the daemon running; does not risk availability. Avoid `mmdiag --all` (very large).

- Short waits under load are normal. The same waiter growing across samples: medium/high.
  Anything above `deadlockDetectionThreshold` (300 s in the book's example) or any
  `--deadlock` output: **page now**.
- Read the waiter reason (SG24-8254): "NSD I/O worker ... I/O completion on disk" = local disk
  I/O (check paths, errpt, SAN); "RPC wait for NSD I/O completion" or "for getData" = network to
  the NSD server; "RPC wait for tmMsgRevoke" = token held on another node; node-recovery waiters
  = ask where the cluster manager is (`mmlsmgr -c`).
- `mmdiag --network`: broken connections or pending messages = medium/high.

## 6. Capacity (carefully)

`mmdf <fs> --block-size auto` is **I/O intensive** (GC28-3197): run once, off-peak, one file
system, on request only, and never with `--qos other`. Prefer `df -g` on the mount point for a
quick look, or mmhealth capacity thresholds (warning 80%, error 90% by default). Inodes below 5%
free is serious (MMFS_SYSTEM_WARNING). `mmlsfileset <fs>` lists filesets (Linked/Unlinked); avoid
`-d` and `-i` (can take hours).

## 7. Logs and error log

`tail -n 500 /var/adm/ras/mmfs.log.latest`. Severity tags: `[I]` info, `[N]` notice, `[W]`
warning, `[E]` error, `[S]` severe, `[X]` exception (report to IBM). `6027-300 mmfsd ready` =
daemon up; `6027-665 ... Connection refused` = daemon down.
AIX `errpt` labels for resource `mmfs`: **page now** for MMFS_FSSTRUCT, MMFS_SYSTEM_UNMOUNT,
MMFS_DISKFAIL, MMFS_ABNORMAL_SHUTDOWN; medium for MMFS_LONGDISKIO, MMFS_SYSTEM_WARNING;
MMFS_ENVIRON points outside GPFS (usually network).

## 8. Context (light, run once)

`mmlscluster` (refreshes the node's local config copy, so not in a loop), `mmlsconfig`,
`mmlsconfig tiebreakerDisks`, `mmlsmgr -c`, `mmlsnsd -X`.

## Never run

Lifecycle and config: `mmstartup`, `mmshutdown`, `mmchconfig`, `mmchnode`, `mmaddnode`,
`mmdelnode`, `mmchmgr`, `mmchlicense`. Disks: `mmchdisk`, `mmadddisk`, `mmdeldisk`, `mmrpldisk`,
`mmcrnsd`, `mmdelnsd`, `mmnsddiscover`. File systems: `mmmount`, `mmumount`, `mmchfs`,
`mmrestripefs`, `mmdefragfs`, `mmfsctl`, `mmapplypolicy`, **`mmfsck` in any form** (even `-n`
can panic an offline file system). Quotas and filesets: `mmcheckquota`, `mmedquota`,
`mmsetquota`, `mmlinkfileset`, `mmunlinkfileset`, snapshot create/delete. Service tools:
`mmfsadm`, `mmdsh`, `gpfs.snap` and `mmnetverify` (L2/IBM only), `mmpmon`. mmhealth write forms:
`--resync`, `eventlog --clear`, `event hide|unhide|resolve`, `thresholds add|delete`,
`config ...`.
