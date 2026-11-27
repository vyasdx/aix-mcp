# Live read-only commands for a human (performance)

Use when the problem is happening now and the daily history does not show it yet. Use an
interval and a count; never start interactive or recording tools. Root is not needed for most
of these on AIX *(verify for your RBAC setup)*.

## CPU

| Command | Read |
|---|---|
| `lparstat -i` | `Type` (shared/dedicated, SMT), `Mode` (capped/uncapped), `Entitled Capacity`, `Online Virtual CPUs`, `Variable Capacity Weight`, `Active CPUs in Pool`, online vs desired values |
| `lparstat 2 10` | `%user %sys %wait %idle physc %entc lbusy app vcsw phint`; header has `smt lcpu ent` |
| `vmstat 2 10` | `kthr r b`, `cpu us sy id wa pc ec` |
| `mpstat -s 2 5` | Use of each SMT thread: one busy thread means a single-threaded workload |
| `sar -P ALL -f /var/adm/sa/saDD` | Past day per CPU, only if sar collection is enabled |
| `ps -eo pid,user,pcpu,pmem,etime,comm,args \| sort -rnk 3 \| head -30` | Top CPU processes |
| `smtctl` (no flags) | SMT mode (any flag changes it) |

Read: capped at %entc ~100 = ceiling; uncapped physc = online VPs = VP ceiling; `app` near 0 =
pool exhausted; `lbusy` near 100 = could use more VPs; `%nsp` is speed vs nominal (above 100 =
running faster, below 100 = throttled); `r` persistently above logical CPUs =
queueing; high `wa` with high `r` = look at disk.

## Memory and paging

| Command | Read |
|---|---|
| `vmstat 2 15` | `avm` (4 KB pages; ÷ 256 = MB), `fre`, `pi`, `po`, `fr`, `sr` |
| `vmstat -v` | `numperm`, `minperm`, `maxperm`, `computational pages %`, `pinned pages`, and the "blocked with no pbuf/psbuf/fsbuf" counters (take two samples) |
| `svmon -G -O unit=MB` | `size inuse free pin virtual available`; paging space `size inuse` |
| `svmon -P -O unit=MB,sortseg=pgsp \| head -40` | Processes using the most paging space (root) |
| `ps -eo pid,user,vsz,rss,comm,args \| sort -rnk 3 \| head -30` | Largest processes |
| `lsps -a` | Each paging space: size, `%Used`, active, auto |
| `lparstat -i \| grep -i memory` | Online vs desired memory, memory mode (dedicated, AMS, AME) |
| `lparstat -m 1 1` | Memory and I/O entitlement: `iomaf` should be 0 |
| `lparstat -c 1 1` | AME only: `%xcpu`, `xphysc` (CPU spent compressing), `dxm` (expansion deficit). Errors out when AME is off |

Read: `pi`/`po` above 0 sustained = paging; `avm` above ~95% of real memory = expect paging
(SG24-8062); `virtual` near or above `size` in svmon = same signal.

## Disk

| Command | Read |
|---|---|
| `iostat 2 10` | `% tm_act`, `Kbps`, `tps` per disk |
| `iostat -D 2 5` | read/write `avgserv`, `maxserv`, `timeouts`, `fails`; queue `avgtime`, `avgwqsz`, `avgsqsz`, `sqfull` |
| `lsattr -El hdiskN -a queue_depth -a max_transfer` | Queue settings |
| `fcstat fcsN` | Adapter resource counters (0 healthy) |
| `lspv`, `lsvg -l <vg>` | Which VG and filesystem sit on a hot disk |

## Recordings that already exist (read only, do not start new ones)

- AIX persistent recording: `/var/perf/daily/<host>_YYMMDD.topas` (what aix-mcp reads).
- sar files: `/var/adm/sa/saDD` if sa1/sa2 are enabled in adm's crontab.
