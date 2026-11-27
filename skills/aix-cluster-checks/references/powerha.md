# PowerHA SystemMirror: read-only checks

Source: IBM Redbook SG24-7739, PowerHA SystemMirror for AIX Cookbook (3rd ed., PowerHA 7.2.7).
Paraphrased. On PowerHA 7.3 re-check flags and state names *(verify)*. Run as root on a cluster
node. Utilities live in `/usr/es/sbin/cluster/utilities/`.

## Minimum set (run on one node)

```sh
lssrc -ls clstrmgrES | grep -i state
/usr/es/sbin/cluster/utilities/clRGinfo
/usr/es/sbin/cluster/utilities/clshowsrv -a
lscluster -m
clmgr -a UNSYNCED_CHANGES query cluster
```

## 1. Cluster manager state: `lssrc -ls clstrmgrES`

`lssrc -s clstrmgrES` showing "active" says nothing: the daemon runs whenever PowerHA is
installed. Use the long form. All nodes at once: `clcmd lssrc -ls clstrmgrES | grep -i state`.
The output also shows `CLversion`, which must be the same on all nodes.

| State | Meaning | Severity |
|---|---|---|
| `ST_STABLE` | Running, resources online | OK |
| `ST_INIT` | Configured, cluster services not active on this node | high if the node should be active; info if planned |
| `NOT_CONFIGURED` | Not configured or not synchronised | high (page now if the node hosts resource groups) |
| `ST_JOINING`, `ST_VOTING`, `ST_RP_RUNNING`, `ST_BARRIER`, `ST_CBARRIER` | Event processing in progress | info; re-check; escalate if still there after ~10 minutes |
| `RP_FAILED` | An event script failed | **page now**; collect the hacmp.out tail |
| `ST_UNSTABLE` | Cluster unstable after an event error | **page now** |

## 2. Resource groups: `clRGinfo`

`/usr/es/sbin/cluster/utilities/clRGinfo` (`clfindres` is the same command). Display flags:
`-v` verbose, `-s` or `-c` colon-separated, `-p` node with temporary highest priority,
`-m` application monitor status, `-t` timers (needs the local cluster manager), `-i` admin
operations.

| RG state | Meaning | Severity |
|---|---|---|
| `ONLINE` | Running (one node for non-concurrent; all intended nodes for concurrent; `ONLINE SECONDARY` on the remote site with GLVM) | OK, but **medium** if on an unexpected node |
| `OFFLINE` | Not running, no error | high if it should be up |
| `UNMANAGED` | Services stopped with Unmanage: resources run without HA protection | high outside a maintenance window |
| `ACQUIRING`, `RELEASING` | Moving | info; re-check |
| `ERROR` | Acquire failed, application start and fallover failed, or a shared VG failed | **page now** |
| `TEMP ERROR` | Recoverable error | high |
| `UNKNOWN` | State not obtainable (communication lost, nodes down) | high to page now |

## 3. Subsystems: `clshowsrv`

`clshowsrv -a` (clstrmgrES, clinfoES, clcomd) or `clshowsrv -v` (also RSCT and CAA).
Healthy per node: cluster services `NORMAL` (`ST_STABLE`), remote communications `UP`,
Cluster-Aware AIX `UP`, and cthags, ctrmc, clstrmgrES, clevmgrdES, clconfd, clcomd active.
clinfoES is optional (only needed for clstat and clinfo clients).

## 4. CAA, heartbeat and repository disk

| Command | Healthy |
|---|---|
| `lscluster -m` | Every node `State of node: UP`, `Reason: NONE`; remote nodes have points of contact UP |
| `lscluster -i` | Interfaces UP (SAN heartbeat `sfwcom` only if configured) |
| `lscluster -c` | Cluster config, number of disks, repository disk |
| `lspv \| grep caavg_private` | Repository disk in `caavg_private`, `active` |
| `lsvg -l caavg_private` | caalv_private1/2/3 and powerha_crlv present |
| `/usr/es/sbin/cluster/utilities/cltopinfo` | Cluster name, heartbeat type (unicast/multicast), repository disk, nodes, networks, RG policies |

A node not UP: **high** (page now if it should run services). Repository not accessible:
**page now**. CAA halts a node that loses the repository to protect data, and cannot start
cluster services at boot without it. No backup repository disk: **medium** (single point of failure).

## 5. Sync, level and config

| Command | Healthy |
|---|---|
| `clmgr -a UNSYNCED_CHANGES query cluster` | `UNSYNCED_CHANGES="false"`. `true` = changes made but not synchronised: **medium** (high if failover depends on them) |
| `clmgr query cluster \| egrep "SPLIT\|MERGE"` | A split and merge policy is set |
| `halevel -s` | Same level on all nodes |
| `lslpp -l cluster.*` | Same filesets on all nodes |
| `df -m /var` | PowerHA logs need room; a full /var breaks event logging |
| `cat /usr/es/sbin/cluster/netmon.cf` | Present on nodes with one adapter per virtual network |

## 6. Logs (read with `tail`/`grep`, never clear)

| File | Use |
|---|---|
| `/var/hacmp/log/hacmp.out` | Event detail. `egrep "EVENT START\|EVENT COMPLETED" /var/hacmp/log/hacmp.out \| tail -40`; a non-zero code at the end of EVENT COMPLETED, or `config_too_long`, means trouble |
| `/var/hacmp/adm/cluster.log` | Timeline of events and errors |
| `/var/hacmp/log/clutils.log`, `/var/hacmp/log/autoverify.log` | Did the nightly verification pass? |
| `/var/hacmp/clverify/fail/` newer than `/pass/` | Last verification failed: **medium**/high |
| `/var/log/clcomd/clcomd.log` | Inter-node communication failures |
| `/var/hacmp/log/cspoc.log` | Who changed what with C-SPOC |

Event names: `node_down`, `network_down_global`, or `rg_move` followed by RG ERROR = **page
now**. `swap_adapter`, `fail_interface`, `fail_standby` = **high** (redundancy reduced).

## Never run

`clmgr` start/stop/online/offline/move/sync/add/modify/delete/manage/replace; `clRGmove`;
`clmgr verify cluster` (can auto-fix; L2 only, with FIX=no); `clmgr view report` with a file;
`clanalyze` and `clsnap` (write files; L2 only); `cl_ezupdate`; cluster test tool; `clusterconf`;
`smitty` sysmirror, cspoc, clstart, clstop or any `cl_*`/`cm_*` menu; `startsrc`, `stopsrc` or
`refresh` on cluster daemons; edits to `/etc/cluster/rhosts`, `netmon.cf`, `clhosts`,
`/etc/snmpdv3.conf`; `clstat` without `-o` (interactive); `qha` (third-party download).

Before handing over for a change, check the book's preconditions: same PowerHA level on all
nodes, no node UNMANAGED, cluster stable, no recent event errors or `config_too_long`.
