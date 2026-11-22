# Performance history at the OS level

## You probably already have it

A default AIX install starts a **persistent local recording** at boot, from the `xmdaily` entry
in `/etc/inittab`. This was seen on AIX 7.3 TL4; please report what older levels do. On an AIX
7.3 TL4 LPAR on PowerVS the entry was:

```
xmdaily:2:once:/usr/bin/topasrec -L -s 300 -R 1 -r 6 -o /var/perf/daily/ -ypersistent=1
```

That writes one binary file a day, `/var/perf/daily/<host>_YYMMDD.topas`, with a snapshot every
**300 seconds**. On that LPAR a full day was 2.3 MB. The files are world-readable, and
`topasout -a <file>` turns a day into **nmon-format CSV** (the format nmon analyser reads):

| Section | Metrics used by aix-mcp |
|---|---|
| `CPU_ALL` | user, sys, wait and idle % |
| `LPAR` | physc (PhysicalCPU), entitled capacity, virtual CPUs, logical CPUs, pool idle |
| `MEMREAL` | memory size, free, %comp, %noncomp |
| `MEMVIRT` | paging space % used, page-ins and page-outs |
| `PROC` | run queue (Runnable) |
| `DISKBUSY` | %busy per hdisk (DISKREAD, DISKWRITE, DISKXFER and DISKSERV are also there) |

The same CSV also has `LAN`, `IP`, `TCPUDP`, `FILE`, `JFSFILE` and `JFSINODE`. The default
recording has **no FC adapter sections**; for FC throughput history you need nmon with `-^`.

So you do not need nmon from cron to get a trend. Check which hosts have the recording:

```sh
lsitab xmdaily; ls -l /var/perf/daily
```

How many days are kept depends on the `topasrec` options. Check them on your own hosts before
relying on a set number of days.

## nmon recordings

If you already run nmon (`nmon -f -s 300 -c 288 -m /var/perf/nmon` or similar), its `.nmon` files
use the same format. Put them in the evidence directory (`<evidence>/<host>/perf/`) and aix-mcp
reads them as well.

## What aix-mcp does with it

`aix-mcp collect` fetches each day once through the dispatcher's `perf day YYMMDD` verb. This
needs no root: the dispatcher converts a private copy with `topasout`. The server then summarises
each day:

* **avg, p95 and max** for CPU busy, physc, run queue, %comp, paging space used and page-outs;
* **% of the day above entitlement**, which shows uncapped LPARs living on borrowed capacity;
* the **peak hour** for physc;
* the **busiest disks** by p95 %busy.

| Tool | Use it for |
|---|---|
| `aix_perf_summary(host, days)` | "How has host-07 looked this week?" |
| `aix_perf_top(metric, days)` | "Top 10 LPARs by physc p95", "who is over entitlement most of the day", "worst paging space" |
| `aix_perf_findings(host?, days)` | CPU at the virtual CPU ceiling, run queue over 2× logical CPUs, paging-space I/O, %comp ≥ 90, disk %busy p95 ≥ 70, and very low use against entitlement (a rightsizing hint) |

Thresholds are conservative and are stated in each finding. They are observations, not
verdicts. Five-minute averages hide short spikes, so say that when you use them.
