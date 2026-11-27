# Triage flows (read-only; each step only observes)

Thresholds marked *(site rule)* are working rules from field practice, not IBM numbers. Tune
them to the estate.

## 0. "Server is slow" (L1 → L2)

1. Scope: one user, one application, one host, or many hosts? Any change in progress or in the
   last 24 hours?
2. History: `aix_perf_findings(host, days=7)`, `aix_perf_summary(host, days=7)`.
3. Live picture (human, see live-commands): `uptime`, `errpt | head -50`, `lparstat -i`,
   `lparstat 2 10`, `vmstat 2 10`, `iostat 2 10`, `svmon -G`, `df -g`, `lspath | grep -v Enabled`.
4. Classify by the first strong signal:
   - physc or %entc at the ceiling, or run queue high with low I/O wait → **CPU** (1).
   - page-outs sustained, paging space rising → **memory** (2).
   - I/O wait high, blocked threads, CPU moderate → **disk** (3).
   - a filesystem at 100% or ENOSPC errors → **aix-filesystem-full**.
5. Neighbours: other LPARs on the same VIOS pair or frame alerting within 30 minutes → shared
   infrastructure; merge incidents; check the VIOS.
6. Compare with the baseline (previous days in aix-mcp history) before concluding.
7. Layer ladder for the note: application → AIX → VIOS → HMC profile → frame/firmware → SAN/network.

## 1. CPU high

1. One process or application above ~60% CPU for more than 10 minutes *(site rule)*? → name it
   and route to the application owner. L1 never kills a process.
2. High I/O wait or run queue with low user CPU? → not CPU; go to disk (3).
3. Neighbours on the same frame or VIOS alerting? → shared cause; merge.
4. Entitlement:
   - **Capped** and %entc pinned at ~100 → hard ceiling; sizing change needs approval (L2).
   - **Uncapped**, physc pinned at the VP count (`perf_vcpu_ceiling`) → VP ceiling; more VPs
     (and EC) needed, L2 sizing.
   - Uncapped, %entc above 100, pool has spare (`app` > 0 in `lparstat`) → allowed; sizing
     review only.
   - Pool has no spare (`app` near 0) → frame-level contention, L3.
   - SG24-7590 lists five reasons %entc can sit at ~100: dedicated CPUs, capped, uncapped with a
     single VP, at the profile maximum, or at the pool maximum.
5. Extra signals: `lbusy` near 100 → more VPs could help; one logical CPU at 100% with low
   `lbusy` → single-threaded workload, more cores will not help; `%nsp` below 100 → cores running
   below nominal frequency.
6. `%sys` dominant with no heavy process → kernel or driver suspicion, L2/L3. (Trace tools such
   as perfpmr are heavy and L3 only.)

## 2. Memory and paging

1. Computational below ~90%, no page-outs, large file cache → **not an incident**: explain that
   AIX uses free memory as file cache. Close with a note.
2. Paging space full but page-in and page-out near zero → **hygiene** (old pages parked in paging
   space). L2 may extend paging space as a planned change.
3. Page-outs sustained (> ~100 pages/s for 10 minutes *(site rule)*; aix-mcp flags p95 > 10/s) and
   paging space above 50% → **real pressure**, continue.
4. Memory reduced by DLPAR in the last 7 days? → change-related; attach the change.
5. One process growing day over day (compare `svmon -P` across days) → leak suspect; application
   owner + L2. Never call a leak from one snapshot.
6. Pinned memory above ~80% of real *(site rule)* → a pinned database cache or similar; DBA/L2,
   not "add RAM".
7. Only one paging space (hd6) and nothing else → design fix, L2. Best practice: one paging LV per
   disk and equal sizes so one does not fill first (SG24-8453).
8. Shared memory (AMS) or Active Memory Expansion: check hypervisor paging and compression CPU
   (live-commands).
9. No rule matched → L2 with the 7-day history.

Guard rails: no permanent memory decision from one snapshot; never remove the active paging
device in business hours.

## 3. Disk slow

1. Any disk with no Enabled path → **page now** (outage). Use **aix-storage-paths**.
2. Paths failed on one VIOS side → redundancy lost; freeze storage changes; L2.
3. Paths fine: read per disk the service time (`avgserv`, `maxserv`), wait queue (`avgwqsz`,
   `avgtime`), `sqfull`, `timeouts` and `fails` (`iostat -D`; on VIOS `viostat -extdisk`).
   - `timeouts` or `fails` above 0 → path or storage fault, not tuning (**high**).
   - `sqfull` above 0 and `avgwqsz` growing → queue depth limit reached; report `queue_depth`
     and `max_transfer` (client must match the VIOS backing disk); L2 with the storage vendor.
   - All paths Enabled but high service time → latency at VIOS or array; check both VIOS and the array.
4. FC adapter resource counters rising (`fcstat`) → adapter limits; L2 with vendor.
5. Map the hot LUN to its VG and filesystem (`lspv`, `lsvg -l <vg>`) so the owner is clear.
6. Several hosts slow through the same adapter or VIOS → fabric or storage, L3. A path change
   within 2 hours of a storage change → attach the change.

No latency thresholds come from IBM sources. As a rough field guide, read service times well
above ~10 ms on flash or cached SAN LUNs deserve a look; always compare with the host's own history.
