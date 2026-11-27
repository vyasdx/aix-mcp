# WPAR: read-only checks

**Status:** commands and state letters checked against `man lswpar` on AIX 7.3 TL4 (November
2026). Output from real WPARs has not been seen yet: column layouts marked *(verify)*. Run in the
**global** environment as root.

## Commands

| Command | Read |
|---|---|
| `lswpar` | Name, State, Type, Hostname, Directory *(verify layout)*. No output when no WPARs exist |
| `lswpar -c` | Colon form: `name:state:type:hostname:directory` |
| `lswpar -s B` | Only WPARs in one state (letters below; several allowed) |
| `lswpar -L <name>` | Full detail for one WPAR |
| `lswpar -M <name>` | Mounts (file systems) |
| `lswpar -N <name>` | Network |
| `lswpar -R <name>` | Resource controls |
| `lswpar -D <name>`, `-G`, `-S` | Devices, general, security privileges |
| `uname -W` | WPAR id; 0 means you are in the global environment |
| `df -g` | WPAR file systems appear under `/wpars/<name>` |
| `errpt \| head -50` | WPAR start failures are logged in the global environment |

## States (from `man lswpar`, AIX 7.3 TL4)

| Letter | State | Severity |
|---|---|---|
| A | Active | OK |
| D | Defined (not started) | info if intended down; high if it should run |
| L | Loaded | info; re-check |
| T | Transitional (starting, stopping) | info; escalate if stuck |
| F | Frozen | medium if unexpected |
| P | Paused | medium if it persists |
| M | Moving (relocation) | info; escalate if stuck |
| N | Maintenance | medium unless a maintenance window is open |
| B | Broken | high (**page now** if production) |
| E | Error | high |

Types: S = system WPAR, A = application WPAR.

## Never run

`mkwpar`, `startwpar`, `stopwpar`, `rebootwpar`, `rmwpar`, `chwpar`, `wparexec`, `savewpar`,
`restwpar`, `syncwpar`, `syncroot`, `movewpar`, and `clogin` (interactive login into a WPAR).
