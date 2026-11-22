# Roadmap

Priorities follow user feedback. Open an issue to argue for a change.

## v0.1: evidence mode (now)

- [x] Storage, multipath, FC and VIOS mapping collector, with watchdog and budget
- [x] Synthetic fixture tests for VIOS, PowerPath and SDDPCM
- [x] MCP server over stdio with six read-only tools
- [x] Typed output schemas, paging cursors, evidence age and a per-call audit log with `traceparent`
- [ ] First external testers on AIX 7.2 and 7.3 and on VIOS 3.1 and 4.1

## v0.2: live collection over SSH

- [x] Forced-command dispatcher (`dispatch`) with a fixed set of verbs, lab-tested against injection and forwarding
- [x] Installer: key-only non-root user, `restrict` + `from=` key, one exact sudo rule checked by `visudo`
- [ ] RBAC alternative to sudo (lab test pending)
- [ ] An Ansible role that deploys the dispatcher, keys and collectors
- [x] `aix-mcp collect`: parallel pull with per-request timeouts, strict host keys, incremental perf days
- [x] Performance history from the AIX persistent recording (`topasout -a`), with summaries, rankings and findings

## More collectors

- [ ] VG and LV capacity, stale partitions and quorum
- [ ] `errpt` summary (counts by class and label, no free text by default)
- [ ] Paging, memory and CPU entitlement snapshot
- [ ] Fileset consistency (`lppchk -v`) and interim fixes (`emgr -l`)

## Transport and release

- [ ] Streamable HTTP at `/mcp` with authentication, for shared deployments
- [ ] PyPI release through trusted publishing, with attestations
- [ ] Signed collector bundle (checksum file and signature)
