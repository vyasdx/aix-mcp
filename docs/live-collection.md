# Live collection over SSH (v0.2)

v0.2 can pull evidence from AIX hosts itself, so you no longer have to copy `.kh` files by hand.
The flow is:

1. `aix-mcp collect` runs on the management server. You run it from cron, AAP or by hand.
2. It connects over SSH to a non-root user on each host.
3. That user's key is tied to a forced command, `/opt/aixmcp/bin/dispatch`. It answers a fixed
   set of verbs and nothing else.

The **MCP server never holds the SSH key**. It still only reads the evidence directory, so an AI
client cannot cause a login to any host.

```
 cron / AAP ── aix-mcp collect ──ssh (key A)──▶ aixmcp@host: forced command dispatch
                     │                                   ├─ storage → sudo (1 exact rule) → collector
                     ▼                                   └─ perf    → /var/perf/daily + topasout (no root)
             evidence directory ◀── reads ── aix-mcp serve ◀── MCP client
```

## What the dispatcher allows

| Request | What runs on the host | Root? |
|---|---|---|
| `version` | Prints the dispatcher version, the short host name and the collector version | no |
| `storage` / `storage quick` | `sudo -n /opt/aixmcp/libexec/aix_storage_paths.ksh -k [-q] -o /var/aixmcp/storage` | yes, through one exact sudo rule |
| `perf list` | `ls -l /var/perf/daily`: lists the days that have recordings | no |
| `perf day YYMMDD` | Copies that day's recording to `~aixmcp`, runs `topasout -a` on the copy, prints the CSV, then deletes the copy | no |

Anything else is refused. That includes an empty request, upper case, `;`, `$()`, `..`, any
option such as `-x`, and any request longer than 32 characters. Every request is sent to syslog
(`user.info`, tag `aixmcp-dispatch`) with the address it came from. AIX does not log `user.info`
by default, so add a line to `/etc/syslog.conf` and run `refresh -s syslogd`:

```
user.info /var/adm/aixmcp.log rotate size 1m files 4
```

## Install on a host

Run as root. The installer copies `dispatch` and `aix_storage_paths.ksh` from the directory it
is run in:

```sh
ksh93 install_dispatch.ksh -k aixmcp.pub -f "10.1.2.3,10.1.2.4"
```

`-f` lists the management servers allowed to use the key. It is written into the key's `from=`
option. The installer:

1. Creates the user `aixmcp` with no password, so it can log in with the key only.
2. Installs `/opt/aixmcp/bin/dispatch` and `/opt/aixmcp/libexec/aix_storage_paths.ksh`, owned by
   root with mode 755.
3. Creates `/var/aixmcp/storage`, owned by root with mode 700. The host keeps its own last 10 runs
   there, including the raw output.
4. Writes one `authorized_keys` line:
   `command="/opt/aixmcp/bin/dispatch",restrict,from="…" ssh-ed25519 …`.
   The `restrict` option disables PTYs, port, agent and X11 forwarding, and `~/.ssh/rc`.
5. Adds one sudo rule, checked with `visudo -c` before it goes live:
   ```
   Defaults:aixmcp !requiretty, env_reset
   aixmcp ALL=(root) NOPASSWD: /opt/aixmcp/libexec/aix_storage_paths.ksh -k -o /var/aixmcp/storage, \
                               /opt/aixmcp/libexec/aix_storage_paths.ksh -k -q -o /var/aixmcp/storage
   ```

It needs `sudo` from the AIX Toolbox. It asks `sudo -V` where the policy file lives (normally
`/etc/sudoers` with `@includedir /etc/sudoers.d`).

To remove everything it created: `ksh93 install_dispatch.ksh -r`.

At scale, push the same steps with Ansible or AAP. The steps are idempotent, so an Ansible role
is a thin wrapper (on the roadmap).

## Collect from the management server

```bash
aix-mcp collect hosts.txt --evidence-dir /srv/aix-evidence --key ~/.ssh/aixmcp \
        --parallel 16 --perf-days 7
```

The command:

* uses the system OpenSSH with `BatchMode=yes` and `StrictHostKeyChecking=yes`. Host keys must
  already be in `known_hosts` (or in the file you pass with `--known-hosts`); nothing is
  trusted on first use.
* runs at most `--parallel` hosts at a time, with `--timeout` seconds per request.
* fetches only days it doesn't already have, plus today, which is still growing.
* writes `<evidence>/<host>/<host>_storage_<UTC>.kh`, `<evidence>/<host>/perf/<host>_<YYMMDD>.nmon.csv`
  and a run report, `<evidence>/last_collect.json`.
* exits 1 if any host had an error. Failed requests are listed, never hidden.

Measured on an AIX 7.3 TL4 LPAR on PowerVS:

| | |
|---|---|
| First pass (storage evidence plus 3 days of history) | 5.2 s |
| Next pass (incremental) | 3 s |
| `storage quick` on the host | 0.7 s |
| One day of history | about 290 KB of CSV, converted by `topasout` in 0.02 s |

## Security checks done on the lab LPAR

| Attempt | Result |
|---|---|
| `id`, `storage; id`, `storage $(id)`, `perf day ../../etc`, `STORAGE`, `version -x` | Refused by the dispatcher |
| Interactive login or PTY | Refused: the forced command always runs, and no PTY is given |
| TCP forwarding (`-L`) | `administratively prohibited` |
| `sudo -n /usr/bin/id` as aixmcp | Password required. The rule covers nothing else. |
| The collector run by sudo with other arguments | Password required |
| `AIXMCP_TEST_BIN=/tmp/evil sudo …` | The hook is ignored (`env_reset`, and the collector drops hooks when elevated). The fake binary never ran. |

## Using RBAC instead of sudo (not tested yet)

Sites without sudo can give the collector its privileges through AIX enhanced RBAC instead: an
authorisation, a role that holds it, and `setsecattr -c` on the collector with `euid=0` and
`accessauths`. The collector is ready for this: it ignores the test hooks whenever the real and
effective uid differ. The exact commands will be published once they have been tested on a lab
LPAR.
