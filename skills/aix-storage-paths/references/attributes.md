# Path and adapter attributes: what good looks like

Paraphrased from IBM Redbooks SG24-8062 (PowerVM Best Practices, Table 5-2/5-3 and the
Fibre Channel sections), SG24-7940 (multipathing on the AIX client and VIOS) and SG24-8453
(AIX PCM). **Always report the actual value; defaults changed between AIX levels.**

## Disk (hdiskN)

| Attribute | Expected | Why |
|---|---|---|
| `hcheck_interval` | 60 on client and VIOS | 0 disables health checks, so a Failed path stays Failed. Below the backing disk's `rw_timeout` gains nothing and can back up health checks, slow I/O or hang it. Older vSCSI client disks default to 0; AIX PCM on 7.2 TL3+ defaults to 60. |
| `hcheck_mode` | `nonactive` | Checks paths with no active I/O, including failed ones |
| `hcheck_cmd` | `test_unit_rdy` | Use `inquiry` only when reservation locks are in use |
| `algorithm` | vSCSI client disks: `fail_over` (the only mode vSCSI MPIO supports). NPIV or physical FC: `round_robin` or `shortest_queue` are common | `fail_over` on a many-path FC disk uses one path only (performance, low) |
| `reserve_policy` | `no_reserve` for any disk seen by two VIOS, shared between hosts, or using round_robin/shortest_queue | `single_path` (the AIX PCM default) on such disks blocks the second VIOS or node, or breaks failover |
| `queue_depth`, `max_transfer` | vSCSI client equal to the VIOS backing disk | A client value above the VIOS value causes queuing. Defaults are right in most cases; the storage vendor decides changes |

After a move from SDDPCM to AIX PCM, attributes return to system defaults (queue_depth,
algorithm, reserve_policy). Check them again. SDDPCM is not supported on POWER9 and later
(SG24-8453): a host still on SDDPCM there is a supportability finding.

## FC protocol device (fscsiN)

| Attribute | Expected | Why |
|---|---|---|
| `fc_err_recov` | `fast_fail` with multipath | Fails I/O at once after a link event so MPIO switches paths quickly. Default is `delayed_fail`. |
| `dyntrk` | `yes` | Lets the host follow a target's N_Port ID change after SAN re-cabling. Always on for virtual FC clients. |
| `attach` | `switch` for fabric attach | |

## FC adapter (fcsN)

`num_cmd_elems` and `max_xfer_size`: raise only after analysis, gradually, with the vendor,
and with a reboot. On NPIV, client values must not exceed the VIOS physical adapter's values, or
the client may fail to configure devices or fail to boot (SG24-8062).

## vSCSI client adapter (vscsiN)

| Attribute | Expected (dual VIOS) |
|---|---|
| `vscsi_err_recov` | `fast_fail` (keep `delayed_fail` for a single-path setup) |
| `vscsi_path_to` | 30 (0 disables; a hung VIOS may then not trigger failover) |

## lsmpio `path_status` codes (AIX PCM, SG24-8453 Table 1-1)

| Code | Meaning | Severity |
|---|---|---|
| `Opt`, `Act` | Optimised / active path | OK |
| `Sel` | Selected for I/O now | OK |
| `Non`, `Pas` | Non-preferred / passive controller | Normal on those paths |
| `Fai` | Path has failed. **status can still read Enabled** | high: the hidden-failure signal |
| `Deg` | Degraded; errors seen, PCM avoiding it | high on in-use disks |
| `Rsv` | Unexpected reservation conflict: another host may be using the disk | high (data risk) |
| `Clo` | Closed | medium if only some paths of an open disk |

## Example: a healthy NPIV disk on AIX 7.3 TL4 (lab)

`algorithm shortest_queue`, `hcheck_interval 60`, `hcheck_mode nonactive`, `hcheck_cmd test_unit_rdy`,
`reserve_policy no_reserve`, `queue_depth 32`, `rw_timeout 30`, `timeout_policy fail_path`; on the
fscsi: `fc_err_recov fast_fail`, `dyntrk yes`, `attach switch`. Eight paths over four virtual FC
adapters, half `Sel,Opt` and half `Non` (preferred and non-preferred storage nodes).

## Path counts

About 4 to 8 paths per LUN. More paths make error recovery, boot and device configuration
slower (SG24-8062). With dual VIOS, each disk should be reachable through both.
