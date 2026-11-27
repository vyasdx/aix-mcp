---
name: aix-filesystem-full
description: Read-only investigation of a full or filling AIX filesystem (JFS2 or GPFS mount) with aix-mcp. Use for filesystem usage alerts, "df shows 100%", ENOSPC errors, inode exhaustion, "df says full but du does not", which filesystems are above a threshold across the estate, and whether the volume group has room to extend. Finds the cause and the owner; never deletes, compresses or extends anything.
---

# AIX filesystem full (read-only)

## Ground rules

Read-only. Never suggest `rm`, `mv`, truncation, `compress`/`gzip`, `chfs` (any form),
`defragfs`, `fuser -k`, `kill`, or restarting an application as an L1 action. Cleanup follows
an approved runbook for a **named** directory, done by its owner; extensions are L2 changes with
approval. State `evidence_age_hours`: a filesystem can fill in minutes, so old evidence may be
wrong in either direction.

## Step 1: how full, where, since when

1. `aix_findings(finding_id="filesystem_used", used_pct=90)` for the estate, or with `host=`.
   aix-mcp rates ≥ 90% as `medium` and ≥ 98% as `high`.
2. `aix_host_storage(host, sections=["filesystems","mounts"])`: size, free, used %, and the mount
   class (local, NFS, GPFS, ...). Remote mounts (NFS, CIFS) are full on the **server**, not here.
3. Same filesystem alerted before? Check earlier tickets: more than 3 alerts in 30 days *(site
   rule)* is a capacity design problem, not an L1 ticket.

## Step 2: how serious

- **Page now:** `/`, `/var`, `/tmp` or `/usr` at or near 100% (logins, logging, patching and
  dumps depend on them); a database or application data filesystem at 100% with errors.
- **High:** any production filesystem ≥ 98%, or growing fast.
- **Medium:** 90% to 97% and stable.
- A GPFS (Storage Scale) mount: capacity is a cluster matter. Use **aix-cluster-checks**
  (Storage Scale) and do not run `mmdf` casually; it is I/O heavy.

## Step 3: find the cause (human runs these, read-only)

Run on the alerted filesystem only, never on `/` as a whole:

| Command | Purpose |
|---|---|
| `df -g <fs>` | Usage in GB |
| `df -i <fs>` | Inode use: `%Iused` near 100 with free space = inode exhaustion (many small files) |
| `lsvg <vg>` | `FREE PPs`: is there room to extend at all? (find the VG with `lsfs <fs>` or `lsvg -l`) |
| `du -sg <fs>/* 2>/dev/null \| sort -rn \| head -20` | Which top-level directory grew. Then drill down one level at a time |
| `find <fs> -xdev -size +500M -mtime -1 2>/dev/null` | Large files written in the last day (`-xdev` stays on this filesystem) |
| `fuser -c <fs>` | Processes using the filesystem (read-only form) |
| `lsof +L1` | Deleted files still held open, **only if lsof is installed** (not in base AIX) |
| `errpt \| head -50` | JFS2 or disk errors around the alert |

`du` and `find` read every file under the path: on very large trees they add load. Scope them
to the alerted directory and stop if the host is already slow.

## Step 4: classify

| Pattern | Meaning | Owner |
|---|---|---|
| Growth in a known log or temp directory with a cleanup runbook | Routine | Runbook owner runs the approved cleanup |
| `df` full but `du` adds up to much less | A deleted file still held open by a process: space returns only when the process closes it or restarts | Application owner restarts with approval. L1 cannot act |
| Inodes exhausted, blocks free | Many small files | Application owner |
| VG has free PPs | Extension possible | L2 change with approval |
| VG has no free PPs | Needs storage | Storage request, L2 |
| Repeat alerts | Capacity design | Problem record, L3 |

JFS2 notes (SG24-8453): JFS2 can grow online but not shrink; on a mirrored VG a new or extended
LV is not automatically mirrored, so check `lsvg -l` (PPs = 2 × LPs) after any L2 extension.
Reclaiming thin-provisioned space and defragmenting are changes.

## Step 5: report

Use the hand-off template from **aix-health-check**. Include: filesystem, %used and %Iused,
growth source if found, VG free PPs, any held-open deleted file and its process, the owner, and
"no files were touched".
