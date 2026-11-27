---
name: aix-performance-triage
description: Read-only AIX and PowerVM performance triage with aix-mcp's daily performance history. Use for "server is slow", high CPU, CPU at entitlement or virtual CPU ceiling, run queue, memory pressure, paging space use or page-outs, busy disks, "which LPARs are busiest this week", right-sizing entitlement and virtual processors, and comparing today with previous days. Explains PowerVM terms (physc, entitlement, VP, capped/uncapped) correctly and decides CPU vs memory vs disk vs application.
---

# AIX performance triage (read-only)

## Ground rules

Read-only. Never suggest `kill`, `renice`, `vmo -o`, `schedo -o`, `ioo -o`, `chdev`, `smtctl`
with flags, DLPAR or HMC changes, or starting recorders (`nmon -f`, `topasrec`). See the
never-run list in **aix-health-check**. Entitlement, VP, memory and weight changes are decided by
L2 and done on the HMC under change control. State the history window and evidence age.
**Do not call a memory leak or a sizing change from one day of data.**

## Terms to use correctly (SG24-7590, SG24-8062)

- **physc**: physical cores actually consumed. **Entitlement (EC)**: cores guaranteed.
  **%entc** = physc ÷ EC × 100.
- **Capped**: physc can never exceed EC. **Uncapped**: may use idle pool capacity above EC, up to
  the number of **virtual processors (VP)**. One VP can never use more than one core, so physc
  ≤ VP is a hard ceiling.
- **Logical CPUs** = VP × SMT threads. Use physc and %entc, not raw %idle: under SMT and shared
  processors, tick-based %usr/%sys mislead.
- **Weight** (0 to 255) only matters for uncapped LPARs competing for spare pool cycles.
- **Computational memory** = process working storage and program text. File cache is not
  pressure: AIX uses free RAM as cache. Paging-space **I/O** decides whether memory is short.

## Step 1: what does the history say?

1. `aix_perf_findings(host=<host or omit>, days=7)`.
2. `aix_perf_summary(host, days=7)`: per day avg, p95 and max for CPU busy, physc vs EC and VP,
   run queue, computational memory, paging space used and page-outs, busiest disks.
3. Estate questions: `aix_perf_top(metric=..., days=7)` with `physc_p95`, `physc_max`,
   `cpu_busy_p95`, `pct_time_over_entitlement`, `runq_p95`, `mem_comp_max`, `pgsp_used_max`,
   `pgsp_pageout_p95` or `disk_busy_p95`.

History comes from AIX's own 5-minute recording, converted once per day. **Missing recent
days** usually mean the recorder stopped, most often because `/var` filled up; it then stays
stopped until a reboot. Say so, and route the `/var` issue to **aix-filesystem-full**. Today's live problem may
not be in it yet; then ask a human for the live commands in
[references/live-commands.md](references/live-commands.md).

## Step 2: classify by the first strong signal

| aix-mcp finding (rule) | Means | Go to |
|---|---|---|
| `perf_vcpu_ceiling` (physc p95 ≥ 90% of VP) | Uncapped LPAR pinned at its VP count: more EC alone will not help | CPU |
| `perf_over_entitlement` (above EC ≥ 50% of the day) | Living on borrowed pool capacity; at risk when neighbours get busy | CPU / sizing |
| `perf_run_queue` (p95 > 2 × logical CPUs) | Threads waiting for CPU | CPU, but check disk first (below) |
| `perf_low_utilisation` (p95 < 20% of EC, EC ≥ 1) | Over-sized; capacity can be reclaimed | Sizing (info) |
| `perf_paging_space_io` (page-out p95 > 10/s) | Real memory shortage | Memory |
| `perf_computational_memory` (≥ 90%) | Working set close to real memory | Memory |
| `perf_paging_space_used` (≥ 50%, high ≥ 80%) | Paging space filling | Memory; exhaustion risk |
| `perf_disk_busy` (%busy p95 ≥ 70) | A disk busy most of the time | Disk |

Flows with the exact decision order: [references/triage-flows.md](references/triage-flows.md).

**Important cross-checks**
- High run queue with moderate CPU and high I/O wait is a **disk** problem, not CPU.
- Paging space nearly full but page-in and page-out near zero is **hygiene**, not an incident.
- Capped LPAR at 100% %entc: it is at its ceiling by design. Uncapped at > 100%: fine while the
  pool has spare capacity; a problem when the pool is busy (frame-level contention, L3).
- %busy alone on a SAN LUN proves little; service time and queues decide (see the disk flow).

## Step 3: compare and correlate

- Compare the worst day with the rest of the week: a new pattern or a steady state?
- `physc_peak_hour`: does the peak line up with batch, backup or a change window?
- Several LPARs on the same frame or VIOS pair worsening together: shared cause. Merge them.
- Pair with **aix-storage-paths** when disk findings coincide with path or FC findings.

## Step 4: answer and escalate

Give: the signal, the window, the numbers (avg / p95 / max), the likely layer (application, AIX,
VIOS, HMC profile, frame, SAN) and the owner.
- **Page now:** paging space near 100% with active page-outs (processes will be killed); a
  production LPAR at its ceiling with users affected and the pool exhausted.
- **L2 the same shift:** sustained `perf_vcpu_ceiling` or `perf_run_queue` on production;
  `perf_paging_space_io` with `perf_paging_space_used` ≥ 50%; disk busy with path or FC errors.
- **Capacity review (info/low):** `perf_low_utilisation`, `perf_over_entitlement` without user
  impact, right-sizing suggestions. Give the evidence; do not size from one week alone.
