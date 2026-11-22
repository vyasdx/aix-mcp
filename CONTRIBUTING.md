# Contributing

Thanks for helping. This project is read-only by design. Any change that adds a command must:

1. Add the command to the collector's `ALLOW` list **and** to `docs/commands.md`, and say whether
   it touches devices.
2. Run under the watchdog (`run ID TIMEOUT cmd ...`), never directly.
3. Come with a fixture under `collectors/tests/fixtures/` and expected lines in `expect`.

Python changes need tests (`pytest`). MCP tools must stay read-only, validate their arguments, and
filter on the server, so that estate-wide answers stay small.

Never commit real host names, serials, WWPNs, IP addresses or client data. Fixtures are synthetic
(`host-NN`, `SYN0001`).
