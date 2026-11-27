# Correlation recipes (client LPAR ↔ VIOS ↔ physical port)

All read-only. Prefer aix-mcp evidence; the commands are for a human when evidence is missing.

## 1. "Which VIOS serves this disk path?" (vSCSI)

1. Client: the Failed path's parent is `vscsiN` (from `aix_path_health` / `aix_host_storage` paths).
2. Client: `lscfg -vl vscsiN` gives a location code ending `-V<client id>-C<slot>-T1`.
3. VIOS: in `lsmap -all`, find the vhost whose client partition id is the client's id and whose
   slot pairs with that client slot (the HMC profile shows the pairing).
4. Check that VIOS: `lspath`, `errlog`, `lsdev -type disk`.

## 2. "Which physical port carries this client's NPIV path?"

1. `aix_lpar_identity(host=<client>)` → partition id.
2. VIOS `aix_host_storage(sections=["npiv_maps"])` → row with `client_id` = that id → `vfchost`,
   `fc` (the backing fcsN), `status`, `ports`.
3. VIOS `aix_host_storage(sections=["npiv_ports","fc_links","target_ports"])` → that fcs:
   `fabric` (npiv_ports), speed and port type (fc_links), and `link` state to each target port
   (target_ports, present when the VIOS uses AIX PCM).
4. Client `lsmpio -are` (human): the adapter's `Link State` and connection errors.

End-to-end healthy: `fabric=1` → `LOGGED_IN` → client link Up → client paths Enabled.

## 3. One VIOS side failing on many clients

Many hosts show Failed paths whose parents all lead to the same VIOS (same client slot pattern,
or the same `fcs` on the VIOS). Treat as one incident on that VIOS or its fabric. Check
`aix_findings(host=<vios>)` and the VIOS `fcstat`. Clients stay up on the other VIOS:
redundancy is gone until it is fixed, so freeze other storage changes.

## 4. Dual-VIOS disk identity

For a client disk served by both VIOS, the backing hdisk names can differ between the VIOS.
Compare LUN id or UDID (`chkdev`) on both. A mismatch means the client's two paths do not lead to
the same LUN: **high**, L2 storage.

## 5. With an HMC MCP server

Ask the HMC server for the client's virtual adapters, their slots, and the partner VIOS and
slot. Then confirm the same slots in aix-mcp VIOS evidence. Report both sources. The HMC knows
the configuration; aix-mcp shows what the OS actually sees and its state.

## 6. Disk and network load placement (design, low)

SG24-7940 suggests sending a client's primary vSCSI disk traffic through the VIOS that is the
SEA *backup*, so disk and network load sit on different VIOS. Report it only when asked for a
design review.
