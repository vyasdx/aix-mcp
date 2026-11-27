# NIM: read-only checks

Sources: IBM Redbook SG24-7296 NIM from A to Z (AIX 5.3 era; state strings still current) and
SG24-8453 (AIX 7.2 NIM objects). Paraphrased. Run as root on the NIM master unless noted.

## Minimum set (master)

```sh
lssrc -s nimesis
lsnim -c machines
lsnim -l <client>
lsnim -t spot
lsnim -t lpp_source
```

## 1. Master and client daemons

- Master: `lssrc -s nimesis`. Not active = no NIM operation can run (**high** if an install is planned).
- Client: `lssrc -s nimsh` when the client is defined with `connect = nimsh`.
- Client config: `cat /etc/niminfo` (NIM_NAME, NIM_MASTER_HOSTNAME, ports 1058/1059). Wrong
  master = medium. Rebuilding it (`niminit`, `nimconfig -r`) is a change.

## 2. Objects: `lsnim`

`lsnim` (all), `lsnim -c machines|networks|resources|groups`, `lsnim -t <type>`,
`lsnim -l <object>` (all attributes), `lsnim -a Cstate -a Mstate <machine>`,
`lsnim -a info <client>` (install progress). `lsnim -O <object>` lists allowed operations:
read-only, but do not turn its output into advice.

## 3. Machine states

| Cstate | Meaning | Severity |
|---|---|---|
| `ready for a NIM operation` | Idle, healthy | OK |
| `BOS installation has been enabled` | Install prepared, waiting for network boot | info if planned; **medium** if left behind |
| `Base Operating System installation is being performed` | Install running (`lsnim -a info` shows progress) | info; escalate if no progress |
| `maintenance boot has been enabled` | Maintenance boot prepared | medium if stale |
| `... is being performed` (customization, lppchk, alt_disk_mig) | Operation running | info; escalate if stuck |

- `Cstate_result`: `success` or `reset` are normal; anything else medium.
- `Mstate` (`currently running`, `not running`): the book warns it can be wrong. Never alert
  on Mstate alone (low).
- `sync_required = yes` after an alternate-master takeover: medium.
- Networks: `Nstate = ready for use` is healthy.

## 4. Resources

- Every resource needs `Rstate = ready for use` (medium; **high** if an install is planned).
- SPOT (`lsnim -l <spot>`): `Rstate_result = success`, `oslevel_r`. A SPOT older than the mksysb
  you plan to install does not work (newer is fine): **high** for that install.
- lpp_source: `simages = yes` if it is meant for BOS installs (medium if missing).
- Content views that are allowed (they only display): `nim -o showres <resource>`,
  `nim -o lslpp <object>`, `nim -o fix_query <spot|client>`,
  `nim -o showlog -a log_type=<boot|bosinst|devinst|nimerr|niminst|script|lppchk> <client>`.
  No other `nim -o` operation, and no extra `-a` attributes.

## 5. Network install stuck (LED codes)

Common hangs: **608** (TFTP; check `/etc/tftpaccess.ctl` does not block `/tftpboot`), **611**
(NFS mount failed; check `/etc/exports`), **613** (route problem in the NIM network definition).
Read-only checks on the master: `ls -l /tftpboot` (boot image, client symlink, `<client>.info`),
`cat /tftpboot/<client>.info`, `cat /etc/bootptab` (one entry per client prepared for network
boot; a leftover entry with nothing pending = medium), `grep bootps /etc/inetd.conf`
(uncommented), `df -m /tftpboot` (images pile up; a separate filesystem is recommended).

## 6. Logs

Master: `alog -o -f /var/adm/ras/nimlog` (failed NIM operations). Client:
`alog -o -f /var/adm/ras/bosinstlog`, `/var/adm/ras/devinst.log`, `/var/adm/ras/nim.installp`,
`/var/adm/ras/nim.script`, `/var/adm/ras/nimsh.log`.

## Never run

Any `nim -o` except the four display operations above (including `reset`, `deallocate`,
`allocate`, `bos_inst`, `cust`, `maint_boot`, `update`, `lppmgr`, `remove`, `define`,
`change`); **`nim -o check`** (rebuilds boot images, refreshes lpp_sources) and
**`nim -o lppchk`** (changes Cstate) even though they sound like checks; any `nimclient -o`;
`niminit`, `nimconfig`, `nim_master_setup`, `nimadm`, `nim_move_up`, `nimquery -d`,
`dkeyexch`, `dpasswd`; `smitty nim*`; start/stop/refresh of nimesis, nimsh, inetd, bootpd or
NFS; edits to `/etc/bootptab`, `/etc/inetd.conf`, `/etc/exports`, `/etc/niminfo`; the bootpd
debug procedure.
