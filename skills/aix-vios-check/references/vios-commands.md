# VIOS read-only commands (run as padmin)

Paraphrased from SG24-7590 (VIOS storage and network monitoring), SG24-7940 (VIOS
configuration), SG24-8062 (best practices). The `padmin` restricted shell uses ioscli syntax.

## NPIV

| Command | Read |
|---|---|
| `lsnports` | `name physloc fabric tports aports swwpns awwpns`. `fabric=1` means NPIV-ready. `aports` = virtual ports still free |
| `lsmap -npiv -all` | Per vfchost: `Name`, `Physloc` (slot), `ClntID`, `ClntName`, `ClntOS`, `Status`, `FC name` (backing fcs), `Ports logged in`, `Flags`, `VFC client name` |
| `lsmap -npiv -vadapter vfchostN` | One vfchost |
| `lsdev -dev vfchost*`, `lsdev -dev fcs*` | Device state |

Healthy: `Status:LOGGED_IN`, ports logged in ≥ 1, FC name and VFC client name filled in.
Problem: `NOT_LOGGED_IN` with ports logged in 0 and an empty client name. Possible causes
(field practice): client down or its adapter not configured, no fcs mapped, zoning or WWPN
problem. For Live Partition Mobility both WWPNs of each client adapter must be zoned.

## vSCSI and VIOS disks

| Command | Read |
|---|---|
| `lsmap -all` | Per vhost (`SVSA`): slot, Client Partition ID, and per VTD: `Status`, `LUN`, `Backing device` |
| `lsmap -vadapter vhostN` | One vhost |
| `lsdev -type disk` | All expected disks Available |
| `lspath` | VIOS's own disk paths all Enabled |
| `lsdev -dev hdiskN -attr` | `reserve_policy`, `hcheck_interval`, `algorithm`, `queue_depth` |
| `chkdev -dev hdiskN -verbose` | Disk identity (UDID) to compare across the VIOS pair *(verify flags)* |
| `lsvg rootvg`, `lsvg -pv rootvg` | VIOS rootvg: no stale PPs, no missing disks |
| `bootlist -mode normal -ls` | Both rootvg mirror disks listed |
| `errlog`, `errlog -ls` | VIOS error log (summary / detail) |
| `viostat -extdisk` | Per disk: `timeouts`, `fails`, `avgserv`, `avgwqsz`, `sqfull` |
| `fcstat fcsN` | Adapter resource counters (0 is healthy) and link counters |
| `ioslevel` | VIOS level |

`viostat -extdisk`: `timeouts` or `fails` above 0 = path or storage errors (**high**). `sqfull`
above 0 with a growing `avgwqsz` = queue depth reached (**medium**). Do not keep detailed viostat
running long-term (SG24-8062).

## Shared Ethernet Adapter

| Command | Read |
|---|---|
| `lsmap -all -net` | SEA, its virtual and physical adapters |
| `lsdev -dev entN -attr` | On the SEA device: `ha_mode`, `ctl_chan`, `real_adapter`, `virt_adapters`, `pvid`, `thread`, `accounting` |
| `entstat -all entN \| grep -i priority` | `Priority` and `Active` |
| `entstat -all entN` | Full: `State` (e.g. `PRIMARY`, `PRIMARY_SH` in load sharing), times became primary/backup, control channel |

`seastat -d entN` only works if SEA accounting is already enabled; enabling it is a change.
Never `seastat -c` (clears statistics) and never `chdev ... ha_mode=standby` (that is a manual
failover).

## Client side of network redundancy (AIX LPAR, root)

`entstat -d entN | grep Active` on an EtherChannel/NIB device: healthy shows the primary
channel. Backup channel active while both VIOS are up = **medium** (a virtual adapter's link is
always up, so NIB does not fail back by itself).

## Not for L1

`oem_setup_env` (root shell; needed for `pcmpath`, `mpio_get_config`, `manage_disk_drivers`):
L2 only, and only when the storage vendor or IBM support asks.
