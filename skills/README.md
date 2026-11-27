# aix-mcp skills: AIX admin playbooks for AI assistants

The aix-mcp tools say **what** can be asked. These skills say **how an experienced AIX admin
works**: what to check first, how to read the answer, how serious it is, who owns it, and what
must never be run. Every skill is **read-only**: L1/L2 checking and correlation only.

Each skill is a folder with a `SKILL.md` (the [Agent Skills](https://agentskills.io) format) and
optional `references/` files that the AI opens only when it needs them.

| Skill | Use it for |
|---|---|
| [aix-health-check](aix-health-check/SKILL.md) | Entry point: "is this host healthy", morning check, estate summary, routing, escalation note. References: error log, rootvg, boot list, dump, services, software, time; the never-run list; the hand-off template |
| [aix-storage-paths](aix-storage-paths/SKILL.md) | MPIO path state, Failed/Missing paths, FC adapters, hcheck/reserve/fc_err_recov/dyntrk, pre-VIOS-maintenance checks |
| [aix-vios-check](aix-vios-check/SKILL.md) | VIOS: NPIV login state, fabric readiness, vSCSI maps, client ↔ VIOS ↔ port correlation, dual-VIOS, SEA failover |
| [aix-performance-triage](aix-performance-triage/SKILL.md) | "Server is slow", CPU vs entitlement and VP ceiling, run queue, memory and paging, disk busy, right-sizing |
| [aix-filesystem-full](aix-filesystem-full/SKILL.md) | Full or filling filesystems, inodes, deleted-but-open files, VG headroom, owner |
| [aix-cluster-checks](aix-cluster-checks/SKILL.md) | PowerHA SystemMirror, IBM Storage Scale (GPFS), NIM and WPAR status checks with exact read-only commands |

## Rules every skill follows

1. Read-only. Use aix-mcp tools first. Never run, suggest or compose a state-changing command.
2. Commands for a human come only from the skill's own lists, copied exactly. Items marked
   *(verify)* have not been confirmed on a lab system yet, and the AI must say so.
3. Always state the evidence age. Missing data is "unknown", never "healthy".
4. Severity uses aix-mcp's scale (`info`, `low`, `medium`, `high`) plus **page now** for
   outage-class conditions.
5. Escalate with evidence, using one hand-off format.

## Sources

Written from IBM Redbooks, paraphrased, never copied: SG24-8062 PowerVM Best Practices,
SG24-7940 PowerVM Introduction and Configuration, SG24-7590 PowerVM Managing and Monitoring,
SG24-8453 AIX Enhancements and Modernization, SG24-7739 PowerHA SystemMirror for AIX Cookbook,
SG24-7296 NIM from A to Z, GC28-3197 Spectrum Scale 5.1.1 Command and Programming Reference,
SG24-8254 IBM Spectrum Scale, REDP-5254 Implementing IBM Spectrum Scale. Thresholds marked
*(site rule)* come from field practice, not from IBM. aix-mcp is not affiliated with IBM.

## Try them

**Claude Code.** Copy the skill folders into your skills directory, then connect aix-mcp:

```sh
# macOS / Linux
mkdir -p ~/.claude/skills && cp -r skills/aix-* ~/.claude/skills/
# Windows (PowerShell)
#   Copy-Item -Recurse skills\aix-* $HOME\.claude\skills\
claude mcp add aix -- uvx aix-mcp serve --demo     # synthetic hosts, no AIX needed
```

Then ask, for example:
- "Morning check on the AIX estate."
- "host-01 is slow today. What is going on?"
- "Which disks are running on fewer paths than they should, and which VIOS is involved?"
- "Is vios-01 healthy? Are all NPIV clients logged in?"
- "/var is full on host-01. What do I do?"
- "Give me the read-only commands to check a PowerHA cluster and tell me what to look for."

**Claude apps.** Zip each skill folder (the zip must contain the folder with `SKILL.md`) and
upload it under Settings → Capabilities → Skills, with aix-mcp connected as an MCP server.

**What good looks like:** the AI picks the right skill, calls aix-mcp tools before asking for
commands, quotes the evidence age, ranks by severity, names an owner, and never offers a
command that changes the system. Please report anything else as an issue.

## To verify in a lab (help wanted)

These items are marked *(verify)* in the skills and need confirmation on a real system:
- `errpt -d`, `-N` filters; `sysdumpdev -l`/`-e` output; how `lsvg` shows quorum off;
  `lppchk -v` output when healthy; time-sync commands per AIX level.
- `fcstat` on an AIX LPAR (documented on VIOS); `lsmpio -Sd` flags; `chkdev` flags on VIOS.
- PowerHA 7.3 differences from 7.2.7 (state names, `clRGinfo` flags, `clmgr query` classes).
- `mmhealth` availability on AIX nodes.
- All WPAR commands and state letters.
