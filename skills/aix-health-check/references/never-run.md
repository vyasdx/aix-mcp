# Commands that change state: never run, never suggest during a check

A check only observes. If one of these is needed, the answer is "raise a change for L2", with
the evidence. This list is not complete: **anything not on a skill's read-only list is out of
scope**, even if it looks harmless.

## Devices, paths, adapters
`chdev` (any form, including `-P`, `-U`, VIOS `-perm`), `chdef`, `chpath`, `mkpath`, `rmpath`,
`rmdev`, `mkdev`, `cfgmgr` (including `cfgmgr -l`), `cfgdev` (VIOS), `manage_disk_drivers` with a
change flag, `cache_mgt`, `mkiscsi`.

Looks read-only but is not:
- `lsmpio -o` sends I/O down every path, including failed ones. It is a probe, not a read.
- `bootlist -m normal <disks>` (with a device list) **sets** the boot list. Only `bootlist -m normal -o` reads it.
- `seastat -c` clears per-client SEA statistics.
- `fuser -k` kills processes. Only `fuser -c` reads.
- `smtctl` with `-m`, `-t` or `-w` changes SMT. Only `smtctl` with no flags reads.

## LVM, filesystems, boot, dump
`mkvg`, `extendvg`, `reducevg`, `chvg` (including quorum), `varyonvg`, `varyoffvg`, `importvg`,
`exportvg`, `syncvg`, `mirrorvg`, `unmirrorvg`, `mklvcopy`, `rmlvcopy`, `mklv`, `chlv`, `rmlv`,
`extendlv`, `migratepv`, `crfs`, `chfs` (including `-a size=` and `-a reclaim=`), `rmfs`,
`mount`, `umount`, `fsck`, `defragfs`, `bosboot`, `sysdumpdev` with any flag other than
`-l`, `-L`, `-e`, `sysdumpstart`, `alt_disk_copy`, `alt_rootvg_op`, `alt_disk_install`,
`multibos`, `mkps`, `rmps`, `chps`, `swapon`, `swapoff`.

## Files, processes, services
`rm`, `mv`, `cp` into system paths, `>` or `>>` redirects, `tee`, editors, `compress`/`gzip` of
logs, `kill`, `slibclean`, `renice`, `startsrc`, `stopsrc`, `refresh`, `traceson`, `tracesoff`,
`errclear`, `errlogger`, `errupdate`, `/usr/lib/errdemon` with options, `/usr/lib/errstop`,
`odmadd`, `odmchange`, `odmdelete`, `crontab -e`, `chuser`, `passwd`, `chsec`.

## Tuning
`vmo -o x=y`, `schedo -o x=y`, `ioo -o x=y`, `no -o x=y`, `nfso -o x=y`, `raso -o x=y`,
any `-p`, `-r`, `-d`, `-D` on those, `tunrestore`, `tundefault`, `smtctl -m|-t|-w`,
`lvmstat -e|-d`, `bindprocessor`, `wlmcntrl`.

## Recording and collection (write files, can be heavy)
`topasrec`, `topasout`, `xmwlm`, `nmon -f`, `topas -R`, `perfpmr`, `snap`, `trace`,
`sar -o`. aix-mcp already reads the recordings AIX keeps; do not start new ones.

## Software
`installp` (any, **including `installp -C`**), `geninstall` (including `-k`), `smitty update_all`,
`updateios`, `emgr -e|-r|-c`, `instfix -k|-f`, `lppchk -u`, `rpm -i|-U|-e`, `dnf`/`yum` installs.

## Time
`ntpdate`, `chronyc makestep`, `setclock`, `date <value>`, edits to `/etc/ntp.conf` or chrony files.

## Partition and platform
`shutdown`, `reboot`, `halt`, HMC `chsyscfg`/`chhwres`/DLPAR, any `smitty` fast path (menus mix
views and changes).

## VIOS (padmin)
`chdev -dev`, `mkvdev`, `rmvdev`, `vfcmap`, `cfgdev`, `mirrorios`, `activatevg`, `extendvg`,
`chvg`, `cfgassist`, `viosecure` with change flags, `backupios`, `viosbr` (backup form; `-view`
is read-only), `savevgstruct`, `snap`, and `oem_setup_env` (gives a root shell: L2 only).

Cluster, Storage Scale, NIM and WPAR lists are in the **aix-cluster-checks** skill.
