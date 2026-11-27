---
name: aix-health-check
description: Read-only L1/L2 health check of one AIX host, a VIOS or a whole AIX estate using the aix-mcp tools. Use for "is this host healthy", "morning check", "what is wrong on host-NN", "summarise the estate", or when an alert names an AIX LPAR and you do not yet know which area is affected. Produces a ranked findings list, what is unknown, and an escalation note. Routes to the storage, VIOS, performance, filesystem and cluster skills for detail.
---

# AIX health check (read-only)

Use this skill to answer "is it healthy?" questions about AIX LPARs and VIOS from aix-mcp
evidence, and to write a clean hand-off for L2. It never changes anything.

## Ground rules

1. **Read-only.** Use aix-mcp tools first. Never run, suggest, or compose a command that changes
   state. The full list is in [references/never-run.md](references/never-run.md). If something
   needs fixing, describe the fix in words for L2 under change control.
2. **Commands for a human** come only from the read-only lists in these skills. Copy them exactly;
   do not invent flags. Items marked *(verify)* are not yet confirmed on a lab system: say so.
3. **Say how old the evidence is.** Every aix-mcp answer has `evidence_age_hours`. Quote it.
   Older than 24 hours: say the picture may be stale.
4. **Missing is not healthy.** If `aix_missing_checks` lists a check, that area is *unknown*.
5. **Severity** uses aix-mcp's scale: `info`, `low`, `medium`, `high`. Add **page now** only for
   outage-class conditions listed below.
6. Never ask for passwords, keys or a root shell. Use host names as the tools return them.

## Step 1: scope

- Whole estate or unknown host: call `aix_list_hosts`. Note each host's role (LPAR or VIOS),
  AIX level, evidence age and check counts.
- One host: call `aix_lpar_identity(host)` so the answer can be joined with HMC data
  (partition id and name, machine type-model and serial).

## Step 2: findings and gaps

1. `aix_findings(host=<host or omit for estate>, min_severity="low")`, highest severity first.
2. `aix_missing_checks(host=...)`: what did not answer, with the command to run by hand.
3. `aix_perf_findings(host=..., days=7)`: CPU, memory, paging and disk observations.

## Step 3: classify and route

| You see | Area | Next skill |
|---|---|---|
| `path_not_enabled`, `too_few_paths`, `hcheck_disabled`, `disk_not_available`, `concurrent_vg_reserve`, `fc_err_recov`, `dyntrk`, `fc_link_not_up` | Storage paths and FC | **aix-storage-paths** |
| Host is a VIOS, or `vfchost_not_logged_in`, `npiv_port_no_fabric` | VIOS, NPIV, vSCSI | **aix-vios-check** |
| Any `perf_*` finding, or the ticket says "slow" | Performance | **aix-performance-triage** |
| `filesystem_used` | Capacity | **aix-filesystem-full** |
| Host runs PowerHA, Storage Scale (GPFS), is a NIM master, or hosts WPARs | Clusters and services | **aix-cluster-checks** |
| Error log, rootvg mirror, boot list, dump device, services, software level, time | General AIX | [references/general-checks.md](references/general-checks.md) |

## Step 4: decide the level

**Page now (outage class)**
- Any disk with zero Enabled paths: a `path_not_enabled` finding whose evidence shows
  `enabled` = 0. Do not suggest `cfgmgr`.
- Paths failed for one VIOS side on many hosts at once (shared VIOS, adapter or fabric problem).
- A filesystem at 100% that holds `/`, `/var`, `/tmp`, `/usr` or a database.
- Cluster: a resource group in ERROR, quorum lost, a Storage Scale disk `down`.

**Hand to L2 the same shift:** any other `high` finding; `medium` findings on production hosts;
any `perf_paging_space_used` at `high`; anything you cannot explain.

**L1 can note and close:** `low` and `info` findings that match a known, documented design
(for example `perf_low_utilisation` on a standby LPAR). Record that you checked.

## Step 5: report

Use [references/handoff-template.md](references/handoff-template.md). Always include:
- hosts considered and the evidence age;
- findings ranked by severity, each with the host, subject and the evidence fields;
- what is unknown (missing checks) and the read-only command a human can run to close the gap;
- the suggested owner (storage, VIOS, SAN, application, cluster, capacity) and why;
- a line saying nothing was changed.

## Example

> **Ask:** "Morning check on the estate."
> 1. `aix_list_hosts` → 42 hosts, newest evidence 3 h old, two hosts 30 h old (call out).
> 2. `aix_findings(min_severity="medium")` → `path_not_enabled` high on host-07 hdisk4
>    (1 of 2 paths Failed, parent fscsi1); `filesystem_used` medium on host-12 `/var` 93%.
> 3. `aix_missing_checks` → host-19 `bootinfo_size` timed out (unknown, not healthy).
> 4. Route host-07 to **aix-storage-paths**, host-12 to **aix-filesystem-full**.
> 5. Report with the hand-off template; host-07 goes to L2 storage the same shift.
