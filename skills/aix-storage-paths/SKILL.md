---
name: aix-storage-paths
description: Read-only investigation of AIX disk multipath, MPIO path state and Fibre Channel adapters with aix-mcp. Use when a disk has Failed or Missing paths, fewer paths than expected, after a VIOS or SAN switch reboot, for "is host-NN storage redundant", hcheck_interval, reserve_policy, fc_err_recov or dyntrk questions, or before a planned VIOS or fabric maintenance. Explains what each finding means, how severe it is, which VIOS or adapter is involved, and what L2 should look at.
---

# AIX storage paths and FC (read-only)

## Ground rules

Read-only. Never run or suggest `cfgmgr`, `chdev`, `chpath`, `rmpath`, `mkpath`, `rmdev`,
`lsmpio -o` (it probes every path with I/O) or any other change; see the never-run list in
**aix-health-check**. State `evidence_age_hours`. Missing checks mean *unknown*. Commands for a
human come only from [references/manual-checks.md](references/manual-checks.md).

## Step 1: get the facts

1. `aix_path_health(host=<host or omit for estate>, only_problems=true)`: per disk: driver,
   total paths, Enabled, Failed, other, ALUA-optimised.
2. `aix_findings(host=..., min_severity="low")` and filter to the storage ids:
   `path_not_enabled`, `too_few_paths`, `hcheck_disabled`, `concurrent_vg_reserve`,
   `disk_not_available`, `fc_err_recov`, `dyntrk`, `fc_link_not_up`.
3. For detail on one host: `aix_host_storage(host, sections=["disks","paths","adapters","fc_links","target_ports"])`.
4. `aix_missing_checks(host)`: if `lspath`, `lsmpio` or `fcstat` did not answer, say the path
   picture is incomplete.

## Step 2: read each finding

| Finding (aix-mcp severity) | What it means | Real severity |
|---|---|---|
| `path_not_enabled` (high) | At least one path is Failed, Missing, Disabled or Defined | **page now** if `enabled` = 0 (no I/O path left). **high** if it is rootvg or the last redundant path. |
| `too_few_paths` (medium) | Fewer Enabled paths than expected (default 2) | **high** if the design is dual-VIOS or dual-fabric: one more failure is an outage |
| `hcheck_disabled` (low) | `hcheck_interval=0`: a Failed path never comes back by itself | **medium** before any VIOS or switch maintenance. IBM guidance is 60 with `hcheck_mode=nonactive` (SG24-8062, SG24-7940) |
| `concurrent_vg_reserve` (medium) | Shared (concurrent) VG disk with a SCSI reserve | **high** in a cluster: the other node can lose access. Disks shared by two hosts or two VIOS need `no_reserve` |
| `disk_not_available` (medium) | Disk is Defined, not Available | **high** if it belongs to an active VG |
| `fc_err_recov` (low) | `delayed_fail` instead of `fast_fail` | **medium** on multipath hosts: failover is slow |
| `dyntrk` (low) | `dyntrk=no` | **medium**: a SAN re-cable or N_Port ID change can drop paths |
| `fc_link_not_up` (medium) | Adapter link to a target port is not Up | **high** if all paths of some disk use that adapter |

Background for explaining a finding is in [references/attributes.md](references/attributes.md).

## Step 3: correlate before you conclude

- **Same parent on many disks** (one `fscsiN` or `vscsiN` parent for every Failed path): it is
  one adapter, one VIOS or one fabric, not many disk problems. Raise one incident.
- **Several hosts, same time, same VIOS side**: shared cause. Run **aix-vios-check** on that VIOS
  and merge the incidents.
- **vSCSI client:** find the serving VIOS from the adapter's slot (the `C<slot>` part of the
  location code), then match that slot in the VIOS `lsmap -all` output. Match on slot numbers,
  never on vhost names: the names follow discovery order (SG24-8062).
- **Recent change:** a path change within 2 hours of a storage or zoning change is
  change-related. Ask for the change number.
- **After a VIOS reboot:** Failed paths that did not come back usually mean `hcheck_interval=0`
  on the client (SG24-7590). An Enabled *standby* vSCSI path proves little without health
  checking, because no I/O uses it (SG24-7940).

## Step 4: escalate

- **Page now:** any disk with no Enabled path; rootvg disk with a Failed path and no healthy
  mirror; many hosts losing paths through the same adapter, VIOS or fabric.
- **L2 storage the same shift:** any other Failed or Missing path; single-path disks where the
  design is dual-path; `fc_link_not_up`; reserve-policy problems on shared disks.
- **L2 planned review:** `hcheck_disabled`, `fc_err_recov`, `dyntrk`, path counts outside about
  4 to 8 per LUN (SG24-8062: more paths slow down error recovery and boot).

Use the hand-off template from **aix-health-check**. Suggested owner: storage/SAN for links,
zoning and array ports; VIOS team for one-VIOS-side patterns; AIX L2 for attributes.

## Never

Suggest re-enabling paths, `cfgmgr`, or attribute changes as an L1 action. The attribute fixes
need `chdev`, usually with `-P` and a reboot or an outage window, and vendor agreement.
