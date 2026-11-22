# Design

## Goals

1. Answer operational questions about AIX hosts from evidence: storage paths, adapters,
   filesystems and VIOS mappings.
2. Be safe enough for a production estate and for a security review. It is read-only, needs no
   agent on AIX, and every command it runs is known in advance.
3. Scale to about 1000 LPARs without flooding the model's context. The server filters before it
   answers.
4. Complement HMC-level and PowerVS-level MCP servers rather than duplicate them.

## Architecture

```
 MCP client (IDE assistant, chat app, internal agent)
        |  stdio (v0.1)   /   streamable HTTP + auth (planned)
        v
 aix-mcp server  ---- reads ---->  evidence directory (*.kh files)
 (management tier)                       ^
                                         |  copied by scp / Ansible fetch (v0.1)
                                         |  or pulled over SSH forced command (v0.2)
                                         |
 AIX LPAR / VIOS:  collectors/aix_storage_paths.ksh  (ksh93, base AIX commands only)
```

* The **server never runs on AIX.** AIX needs only ksh93 and base commands, both of which ship
  with the OS.
* **v0.1 is evidence mode.** The server reads files that already exist. This is the simplest
  thing a security team can approve: the MCP server has no credentials to any host.
* **v0.2 adds collection over SSH** through a forced-command key on a non-root user:

  ```
  command="/opt/aixmcp/bin/dispatch",restrict,from="<management hosts>" ssh-ed25519 AAAA...
  ```

  The dispatcher accepts only a fixed set of verbs, such as `storage` and `vg`, and runs the
  matching collector. A small RBAC role or a sudo rule covers the few commands that need root, for
  example `lsmpio` and `fcstat`. The model never supplies a command line, only a verb and a host.

## The join key with HMC-level data

| Guest-OS field | Source on AIX | HMC-level equivalent |
|---|---|---|
| `partition_id` | `uname -L` | LPAR id |
| `partition_name` | `uname -L` | LPAR name |
| `machine_type_model` | `lsattr -El sys0 -a modelname` | managed system MTM |
| `machine_serial` | `lsattr -El sys0 -a systemid` | managed system serial |
| NPIV client WWPNs | `lscfg -vl fcsN` | virtual FC adapter WWPNs |

An agent can take `list_lpar_vfc_adapters` style data from an HMC server and `findings` from
aix-mcp, and say *"LPAR 5 on frame 9105-42A/02SYN0001 has hdisk1 with a failed path on fscsi1,
which maps to vfchost0 on vios-01"*.

## Threat model (short)

The model and the tool arguments it produces are treated as untrusted. The table maps the main
risks, following the OWASP guidance for MCP servers, to what this project does.

| Risk | Mitigation |
|---|---|
| Command injection via tool arguments | No tool takes a command. Host names are validated against `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` and used only as dictionary keys, never in paths or shells. |
| Excessive capability | No write tools exist. Adding one would need a separate server and human approval. |
| Prompt injection from collected data | Evidence is returned as typed fields, not as instructions. Free-text fields (descriptions, notes) are short and come from AIX commands. |
| Data exposure | Evidence holds host names, WWPNs and LUN ids. Keep the evidence directory on the management tier with normal file permissions, and pseudonymise it before it leaves the site. |
| Host impact | Watchdog per command, a run budget, `nice 19`, and no I/O tests. Remote mounts are never touched. |
| Untraceable automation | One JSON audit line per tool call, with tool, arguments, result count, duration and the caller's W3C `traceparent` from `_meta`. It goes to stderr, and to `AIX_MCP_AUDIT_LOG` if that is set. |
| Oversized or mixed results | Every answer is paged (`limit` up to 1000, opaque cursor). A cursor is bound to its tool, its arguments and the evidence snapshot, so it cannot be replayed against other data. |
| Supply chain | One runtime dependency (the MCP Python SDK). Releases are planned through PyPI trusted publishing with attestations. |

## What it will never do

* Run a command chosen by the model.
* Change ODM, run `cfgmgr`, open devices for I/O tests, or read file contents.
* Contact a remote NFS or CIFS server.
* Send data anywhere except back to the MCP client that asked.
