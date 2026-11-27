# Hand-off note template (L1 → L2)

Fill every section. Write "none" rather than leaving one out. Keep raw output in an attachment,
not in the summary line.

```text
SUMMARY      <one line: what is wrong, where, how bad>  e.g. "host-07: 1 of 2 FC paths Failed on hdisk4 (rootvg), redundancy lost"
SEVERITY     <high | medium | low | info>  [PAGE NOW if outage class]
SCOPE        hosts considered: <n>; affected: <list>; role: <LPAR | VIOS>; identity: <partition id/name, MTM-serial>
EVIDENCE AGE <evidence_age_hours> h (collected <collected_at> UTC)

FINDINGS (highest first)
  severity | host | subject | finding id | key evidence
  high     | host-07 | hdisk4 | path_not_enabled | paths 2, enabled 1, failed 1, driver AIX PCM, vg rootvg

UNKNOWN (missing checks)
  host | check | reason | read-only command to close the gap

READ-ONLY COMMANDS RUN BY A HUMAN (if any)
  <exact command> @ <time> → <short result>; full output attached

CORRELATION
  <same VIOS / same fcs / same frame / recent change / repeat alert in last 30 days>

SUGGESTED OWNER   <storage | VIOS | SAN | application owner | capacity | cluster | IBM support> because <reason>
SUGGESTED NEXT    <what L2 should look at first, in words; no commands that change state>

CHANGES MADE      none (read-only check)
```

Rules for the note:
- Facts first, then interpretation. Mark guesses as guesses.
- Quote error log descriptions and recommended actions from `errpt -a` rather than paraphrasing.
- Name the application when known, so the right owner is paged.
- One incident per root cause: if several hosts share one VIOS, adapter or fabric, merge them.
