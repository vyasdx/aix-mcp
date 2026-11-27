---
name: aix-vios-check
description: Read-only check of an IBM Virtual I/O Server (VIOS) and the client LPARs it serves, using aix-mcp evidence. Use for NPIV vfchost login state, physical FC port fabric readiness, vSCSI mappings, "which VIOS serves this LPAR's disks", dual-VIOS redundancy, SEA failover state, and pre/post VIOS maintenance checks. Correlates a client LPAR to its VIOS adapters and physical FC ports, and with an HMC MCP server when one is available.
---

# VIOS check (read-only)

## Ground rules

Read-only. On a VIOS never suggest `chdev -dev`, `mkvdev`, `rmvdev`, `vfcmap`, `cfgdev`,
`mirrorios`, `seastat -c`, backups, or `oem_setup_env` (it gives a root shell; L2 only). See the
never-run list in **aix-health-check**. State `evidence_age_hours`. Commands for a human come
only from [references/vios-commands.md](references/vios-commands.md) and run as `padmin`.

## Step 1: is it a VIOS, and what does it serve?

1. `aix_list_hosts`: the role column says VIOS or LPAR.
2. `aix_host_storage(host=<vios>, sections=["npiv_maps","npiv_ports","vscsi_maps","adapters","fc_links","target_ports"])`.
   NPIV rows carry `vfchost`, `client_id`, `client_name`, `status`, `fc` (backing port) and
   `ports`; vSCSI rows carry `vhost`, `client_id`, `vtd`, `status` and `backing`.
3. `aix_findings(host=<vios>)`: look for `vfchost_not_logged_in`, `npiv_port_no_fabric`,
   `fc_link_not_up`, `path_not_enabled` (the VIOS's own disks) and `filesystem_used`.

## Step 2: read the NPIV and vSCSI picture

| Evidence | Healthy | Problem and severity |
|---|---|---|
| NPIV map status (`lsmap -npiv`) | `LOGGED_IN`, ports logged in ≥ 1, backing `fcs` and client name filled in | `NOT_LOGGED_IN` for a **running** client: that client lost a path through this VIOS (**high**; **page now** if it is the client's only VIOS path). A shut-down or spare client is expected. |
| Physical port (`lsnports`) | `fabric=1` | `fabric=0`: adapter or switch port not NPIV-ready (**high** if vfchosts are mapped to it) |
| vSCSI map (`lsmap -all`) | Each VTD `Available` with a backing device | VTD not Available (**high**); no VTD on a vhost for an active client |
| FC link | `Up` | Not Up (**high** if clients depend on that port) |

Design checks worth reporting (**low** to **medium**, from SG24-8062 and SG24-7940):
- each client has one virtual FC adapter through **each** VIOS;
- one client's vfchosts are not all on the same physical `fcs` (single point of failure);
- disks presented by both VIOS use `reserve_policy=no_reserve` on both;
- boot (rootvg) and data disks are not mapped on the same vhost, and LV, PV and SSP backing are not mixed on one vhost;
- client LV backing devices are not in the VIOS rootvg.

## Step 3: correlate client ↔ VIOS ↔ physical port

Details and examples: [references/correlation.md](references/correlation.md).
- Use **slot numbers** (the `C<slot>` in location codes) and the client partition id. Never
  match on vhost or vfchost names: they follow discovery order (SG24-8062).
- Client partition id comes from `aix_lpar_identity(host=<client>)`. Find it as `client_id` in
  the VIOS NPIV or vSCSI maps. NPIV shows it in decimal; vSCSI `lsmap -all` prints it in hex
  (for example `0x00000005` = 5).
- If an **HMC MCP server** is connected, ask it which VIOS and slots serve the client's virtual
  adapters, then confirm the same slots in aix-mcp evidence. Two sources agreeing is the answer;
  disagreement is itself a finding for L2.

## Step 4: dual-VIOS view

When both VIOS of a pair have evidence, compare them:
- the same clients mapped on both;
- both healthy at the same time (a problem on only one side means redundancy is reduced, not lost);
- the same LUN on both VIOS: hdisk names can differ, so compare LUN id or UDID (`chkdev`).

## Step 5: SEA (network), when asked

aix-mcp does not collect SEA state yet. Give the human the SEA commands in
[references/vios-commands.md](references/vios-commands.md). Healthy failover: primary VIOS
`Priority: 1 Active: True`, backup `Priority: 2 Active: False`; both `ha_mode=auto` (or both
`sharing`) with `ctl_chan` set. **High:** both VIOS active for the same VLANs (loop risk) or
neither active. **Medium:** the backup is active while the primary is up, or the
become-primary/backup counters keep climbing.

## Step 6: escalate

- **Page now:** a running client with no logged-in NPIV path or no available vSCSI path left;
  many clients affected through one VIOS at once; both SEAs active or neither active.
- **L2 VIOS team the same shift:** any `NOT_LOGGED_IN` for a running client, `fabric=0` with
  mappings, VTD not Available, VIOS rootvg stale or missing disks.
- **Planned review:** design findings from Step 2.

Before any VIOS reboot, run the pre-maintenance checklist in **aix-storage-paths**
(manual-checks) on every client. If any client is single-pathed through this VIOS, the reboot is
an outage for that client.
