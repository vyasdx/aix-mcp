# Commands the collector runs

`collectors/aix_storage_paths.ksh` refuses any command whose first word is not on its allowlist
(`ALLOW` in the script). This page lists every command it can run, so a security team can review
the complete list.

| Command | Purpose | Touches devices? |
|---|---|---|
| `oslevel -s`, `uname -L`, `lsattr -El sys0 -a modelname -a systemid -F value` | Host identity and AIX level | No (ODM) |
| `mount` | Kernel mount table; classifies each mount | No |
| `df -k <local and cluster mountpoints only>` | Capacity. Remote mounts are never passed to `df`. | No |
| `lssrc -g nfs`, `cat /etc/exports`, `exportfs` | NFS server state and exports | No |
| `lsdev -Cc disk`, `lsdev -Cc adapter`, `lsdev -p fcsN` | Device inventory | No (ODM) |
| `lspv` | PV to VG mapping | No (ODM) |
| `lspath -F name:parent:connection:path_status:status` | Path state per disk | No (ODM and driver) |
| `lsmpio`, `lsmpio -ar` | AIX PCM path detail and target ports | Driver tables only |
| `manage_disk_drivers -l` | Which driver claims which storage family | No |
| `lsattr -El hdiskN`, `lsattr -El fscsiN` | Path-related attributes | No (ODM) |
| `bootinfo -s hdiskN` | Disk size | Opens the disk. Each call has a 3 s watchdog; checks stop after 3 timeouts. Skipped with `-q`. |
| `lscfg -vl fcsN` | Adapter WWPN | No (VPD in ODM) |
| `fcstat fcsN` | Link speed, port type, attention | Adapter query. Skipped with `-q`. |
| `powermt display dev=all`, `powermt display paths` | PowerPath, only if installed | Driver query |
| `pcmpath query device`, `pcmpath query adapter` | SDDPCM, only if installed | Driver query |
| `dlnkmgr view -path` | HDLM, only if installed | Driver query |
| `vxdmpadm listctlr all`, `vxdmpadm getsubpaths` | Veritas DMP, only if installed | Driver query |
| `ioscli ioslevel`, `ioscli lsmap -all -npiv ...`, `ioscli lsnports`, `ioscli lsmap -all ...`, `ioscli lsmap -all -net` | VIOS mappings, only on a VIOS | No |
| `ps -e -o pid= -o ppid=` | Used by the watchdog to find child processes to stop | No |
| `hostname` | Output file name | No |

## Dispatcher (live collection, v0.2)

`collectors/dispatch` is the forced command for the collection user. Apart from running the
collector above through sudo, it runs only the following:

| Command | Purpose | Root? |
|---|---|---|
| `hostname` | Short host name for the evidence folder | no |
| `sed`, `head` on the installed collector | Report the collector version | no |
| `ls -l /var/perf/daily` | List daily performance recordings | no |
| `cp <recording> ~aixmcp/.aixmcp_perf.<pid>/`, `topasout -a <copy>`, `cat <csv>`, `rm -rf` of that private directory | Convert one day to nmon-format CSV | no |
| `logger -p user.info -t aixmcp-dispatch` | Audit line per request | no |

Requests and how they are refused are described in [live-collection.md](live-collection.md).

## Behaviour on trouble

* **Per-check timeout** (`-t`, default 10 s): a check that runs too long is sent TERM, then KILL.
  It is then abandoned and recorded as `C|<check>|MISSING|...` together with its command line.
* **Run budget** (`-b`, default 120 s): once the budget is used up, no new check starts. Every
  check that was skipped is recorded as `MISSING`.
* **Low priority:** the script runs `renice 19` on itself.
* **No interactive input:** every command's standard input is `/dev/null`.
