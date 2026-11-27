# General AIX checks: read-only commands for a human

aix-mcp does not collect these areas yet. When a ticket needs them, give the admin these exact
commands, ask for the output, and read it with the notes below. Run as root unless noted.
*(verify)* = syntax or output not yet confirmed on a lab system: say so when you use it.
Everything else here was checked on AIX 7.3 TL4 (7300-04-02) in November 2026.

Sources: IBM Redbooks SG24-7590 (PowerVM Managing and Monitoring), SG24-8453 (AIX Enhancements
and Modernization), SG24-7940 (PowerVM Introduction and Configuration), and field practice.
Text is paraphrased.

## 1. Error log

| Command | Purpose |
|---|---|
| `errpt \| head -50` | Newest entries, summary |
| `errpt -a -j <IDENTIFIER>` | Full detail for one identifier |
| `errpt -a -l <sequence>` | Full detail for one entry |
| `errpt -d H` / `errpt -d S` | Hardware / software class only |
| `errpt -N <resource>` | One resource, e.g. `hdisk3` or `sys0` |

**Reading the summary.** Columns are `IDENTIFIER TIMESTAMP T C RESOURCE_NAME DESCRIPTION`.
TIMESTAMP is `mmddhhmmyy`. **T** is the type (`P` permanent, `T` temporary, `I` informational;
read the `Type:` line in `errpt -a` for others). **C** is the class: `H` hardware, `S` software,
`O` operator, `U` undetermined (SG24-7590, error logging).

**Reading a detail entry.** IDENTIFIER (8 hex digits, the event kind), LABEL (searchable name),
Class, Type, Resource Name, Description, Probable Causes, Recommended Actions, Detail Data,
Sequence Number. Count repeats per identifier and resource. Quote the recommended actions.

**Severity**
- **high, page now:** new `P H` on a rootvg disk, on every path of a disk, on memory or processor
  (`sysplanar0`); a burst across many resources in the same minute.
- **high:** new `P H` on a non-rootvg disk or adapter while redundancy remains; the same `T`
  entry repeating on one resource.
- **low:** `S` and `O` entries. **info:** `I` entries that match planned events: SEA
  failover tests, EtherChannel recovery, Live Partition Mobility (resource `pmig`).

Useful identifiers (SG24-7940, SG24-7590): `EAA3D429` physical partition marked stale;
`F7DDA124` physical volume declared missing; `E86653C3` I/O error detected by LVM;
`52715FA5` failed to write VG status; `40D97644` / `E136EAFA` SEA became backup / primary;
`9F7B0FA6` EtherChannel ping to remote host failed on primary.

## 2. rootvg, mirror and LVM

| Command | Read |
|---|---|
| `lsvg rootvg` | `STALE PVs`, `STALE PPs`, `ACTIVE PVs` vs `TOTAL PVs`, `QUORUM`, `FREE PPs` |
| `lsvg -p rootvg` | Every PV `active`; any `missing` is a problem |
| `lsvg -l rootvg` | Each LV: LPs, PPs, PVs, LV STATE |
| `lspv` | Disk to VG map |

**Healthy (mirrored rootvg):** STALE PVs 0, STALE PPs 0, ACTIVE PVs = TOTAL PVs, every LV with
PPs = 2 × LPs on 2 PVs, state `open/syncd` or `closed/syncd`. With client mirroring across two
VIOS, one copy should come from each VIOS, and quorum should be off (SG24-7590, mirroring
environment checks). `lsvg` shows quorum as `QUORUM: 2 (Enabled)`; the disabled form is expected
to read `(Disabled)` *(verify)*.

**Abnormal:** stale PPs (expected right after a VIOS reboot until resync, then a problem);
any PV `missing`; an LV with PPs = LPs in a mirrored VG (new LVs are not mirrored automatically,
SG24-8453). **high** for missing PVs and lasting stale partitions in rootvg. The resync
(`varyonvg`, `syncvg`) is L2 work.

## 3. Boot list

`bootlist -m normal -o` (display only; without `-o` it **sets** the list). VIOS: `bootlist -mode normal -ls`.
`bootinfo -b` shows the disk the system last booted from.

**Healthy:** the rootvg disks, both mirror disks when mirrored, e.g. `hdisk0 blv=hd5 pathid=0`.
On multipath boot disks the same disk appears once per path (`pathid=0`, `pathid=1`, ...): that is normal.
**Abnormal (medium, high if a reboot is planned):** only one disk on a mirrored rootvg; a disk not
in rootvg; a `missing` disk; `blv=bos_hd5` (standby BOS) or `old_rootvg`/`altinst_rootvg`
disks when no change window is open. Check the change record before escalating.

## 4. Dump device

`sysdumpdev -l` lists `primary`, `secondary`, `copy directory`, `forced copy flag`, `always allow dump`,
`dump compression`, `type of dump` (e.g. `fw-assisted`) and `full memory dump`.
`sysdumpdev -L` describes the most recent dump ("No previous dumps recorded" when none).
`sysdumpdev -e` prints the estimated compressed dump size in bytes.
A typical healthy 7.3 result: primary `/dev/lg_dumplv`, secondary `/dev/sysdumpnull`, type `fw-assisted`.

**Abnormal:** primary `/dev/sysdumpnull` (no dump will be taken); dump LV smaller than the
estimate; dump LV on a PV that is currently `missing` (it blocks rootvg recovery, SG24-7940);
`-L` shows a recent dump nobody knew about, meaning an unexplained crash: **high**, keep the
evidence, L2/L3.

## 5. Services

`lssrc -a`, `lssrc -s <subsystem>`, `lssrc -g <group>`, `lssrc -ls <subsystem>`.
`inoperative` means not running. Many subsystems are off by design, so compare with what the
host's role needs (sshd, syslogd, the time daemon, NFS or cluster daemons). Expected service
down: **medium**, or **high** if the role depends on it. Restarts are L2 with a runbook.

## 6. Software level and consistency

| Command | Read |
|---|---|
| `oslevel -s` | `TTTT-TL-SP-YYWW`, e.g. `7300-03-01-2446` |
| `oslevel -rl <target TL>` | Filesets below a target level (explains a "stuck" oslevel) |
| `lppchk -v` | Healthy: no output and return code 0; any lines = inconsistent filesets |
| `instfix -i` | Which TL/SP bundles are complete |
| `emgr -l` | Interim fixes installed ("There is no efix data on this system." when none) |
| `lslpp -l <fileset>` | Installed level of one fileset |

Inconsistent filesets: **medium**, **high** during a failed patch window. Unknown or
undocumented ifixes: **low**, **medium** before a patch (an ifix can lock filesets a TL/SP must
update). A patch is not done until `lppchk -v` and the target level both pass.

## 7. Time sync

AIX 7.3 TL4 uses `xntpd` (there is no `chronyd` subsystem on that level).
`lssrc -s xntpd` (active?), `ntpq -p` (peers, offset, reach), `lssrc -ls xntpd` (sys peer,
stratum; fails when the daemon is not running), `grep -v '^#' /etc/ntp.conf` (configured servers).
Healthy: daemon active, a selected peer, small offset, stratum not 16. `inoperative`, or an
`ntp.conf` with no `server` line, means the clock is not synchronised.
Out of sync on cluster nodes, databases or Kerberos/AD clients: **medium** to **high**.

## 8. Identity (confirm you are on the right LPAR)

`hostname`, `uname -L` (LPAR number and name), `lparstat -i`, `lsattr -El sys0 -a modelname -a systemid`,
`who -b` (last boot), `prtconf` (slow; full summary). aix-mcp's `aix_lpar_identity` returns
the same identity without a login.
