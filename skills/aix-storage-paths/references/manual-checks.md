# Read-only commands for a human (storage paths)

Use when aix-mcp evidence is old, a check is missing, or L2 wants live detail. AIX as root;
VIOS as `padmin`. Ask for the output and read it with [attributes.md](attributes.md).

## AIX client

| Command | Read |
|---|---|
| `lspath` | Every line should be `Enabled hdiskN <parent>` |
| `lspath \| grep -v Enabled` | Only the problem paths |
| `lspath -l hdiskN` | Paths of one disk |
| `lspath -AHE -l hdiskN -p vscsiN` | Path `priority` (1 is highest) |
| `lsmpio -l hdiskN` | `status` and `path_status` per path (AIX PCM) |
| `lsmpio -are` | Per FC adapter: WWPN, `Link State`, remote ports, connection errors (10 min / 60 min / 24 h) |
| `lsmpio -Sd` | Per-path counters: timeouts, transport errors, path failure count *(verify flags on your level)* |
| `lsattr -El hdiskN` | `hcheck_interval`, `hcheck_mode`, `algorithm`, `reserve_policy`, `queue_depth`, `max_transfer` |
| `lsattr -El fscsiN` | `fc_err_recov`, `dyntrk`, `attach` |
| `lsattr -El fcsN` | `num_cmd_elems`, `max_xfer_size` |
| `lsattr -El vscsiN` | `vscsi_err_recov`, `vscsi_path_to` |
| `lscfg -vl vscsiN` / `lscfg -vl fcsN` | Location code (slot `C<n>`), WWPN |
| `fcstat fcsN` | Resource counters and link counters (see below) *(verify on an AIX LPAR; documented on VIOS)* |
| `lsdev -Cc disk`, `lsdev -Cc adapter` | Available vs Defined |
| `errpt \| head -50` | Path and disk errors around the time of the alert |

**Do not use** `lsmpio -o`: it sends I/O down every path, including failed ones.

## fcstat counters

- `No DMA Resource Count`, `No Adapter Elements Count`, `No Command Resource Count`: 0 is
  healthy. Non-zero means I/O queued at the adapter for lack of resources (points at
  `max_xfer_size` or `num_cmd_elems`). Counters run since boot: compare two samples.
- `Link Failure Count`, `Loss of Sync Count`, `Invalid CRC Count` growing between samples
  suggest cabling, optics or switch-port trouble *(interpretation is field practice)*.
- Never use an option that resets statistics.

## Third-party multipath (only if installed)

| Driver | Command (root; on VIOS via `oem_setup_env`, which is L2 only) | Healthy |
|---|---|---|
| SDDPCM | `pcmpath query device`, `pcmpath query adapter` | State `OPEN`, Mode `NORMAL`, Errors 0; `*` marks non-preferred paths |
| PowerPath | `powermt display dev=all`, `powermt display paths` | All paths alive |
| HDLM | `dlnkmgr view -path` | All paths Online |
| Veritas DMP | `vxdmpadm getsubpaths`, `vxdmpadm listctlr all` | All ENABLED |
| Any | `manage_disk_drivers -l` | Which driver claims which storage family |

## Before a planned VIOS reboot (SG24-7590 checklist)

On every client of that VIOS: `lspath` all Enabled; `lsattr -El hdiskN` shows
`hcheck_interval` 60; `lsvg rootvg` shows no stale PPs and quorum off for client mirrors;
`lsvg -p rootvg` nothing missing; NIB `entstat -d entN | grep Active` on the primary channel.
Any gap: do not proceed; hand to L2.
