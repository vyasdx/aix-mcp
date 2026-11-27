# WPAR: read-only checks

**Status: unverified.** The IBM Redbooks used for these skills contain no WPAR technical detail.
Everything here is general knowledge and must be checked against `man lswpar` on AIX 7.2 / 7.3
before relying on it. Say so when you use it. Run in the **global** environment as root.

## Commands *(verify)*

| Command | Read |
|---|---|
| `lswpar` | Name, State, Type, Hostname, Directory |
| `lswpar -L <name>` | Full detail for one WPAR |
| `lswpar -M <name>` | Mounts (file systems) |
| `lswpar -N <name>` | Network |
| `lswpar -R <name>` | Resource controls |
| `uname -W` | WPAR id; 0 means you are in the global environment |
| `df -g` | WPAR file systems appear under `/wpars/<name>` |
| `errpt \| head -50` | WPAR start failures are logged in the global environment |

## States *(verify)*

| Letter | State | Severity |
|---|---|---|
| A | Active | OK |
| D | Defined (not started) | info if intended down; high if it should run |
| L | Loaded | info; re-check |
| T | Transitional (starting, stopping) | info; escalate if stuck |
| F | Frozen | medium if unexpected |
| P | Paused | medium if it persists |
| M | Moving (relocation) | info; escalate if stuck |
| B | Broken | high (**page now** if production) |

Types: S = system WPAR, A = application WPAR.

## Never run

`mkwpar`, `startwpar`, `stopwpar`, `rebootwpar`, `rmwpar`, `chwpar`, `wparexec`, `savewpar`,
`restwpar`, `syncwpar`, `syncroot`, `movewpar`, and `clogin` (interactive login into a WPAR).
