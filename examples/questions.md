# Questions to try

Run these against the synthetic evidence first:

```bash
aix-mcp serve --evidence-dir tests/data
```

**Estate**
- Which hosts do we have evidence for, and how old is it?
- Any disks running on fewer than two working paths?
- Show every high-severity storage finding.
- What could not be collected, and what should I run by hand?

**One host**
- Give me host-01's FC adapters with `fc_err_recov` and `dyntrk`.
- Which VG is hdisk1 in, and is it AIX PCM or a third-party driver?
- On vios-01, which NPIV clients are not logged in, and on which physical port?

**Joined with HMC-level data** (needs an HMC or PowerVS MCP server in the same client)
- For every LPAR with a failed path, show the frame and the VIOS that serves its virtual FC.
