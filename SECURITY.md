# Security policy

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting**: open the Security tab of this repository
and choose "Report a vulnerability". Do not open a public issue for security problems.

## Scope

In scope:
- the MCP server;
- the collectors;
- anything that could make them change a host, read data they should not, or run a command that
  is not on the documented list in [docs/commands.md](docs/commands.md).

## Supported versions

Only the latest release gets fixes during pre-alpha.

## Handling evidence

Collector output contains host names, WWPNs and LUN ids. Never attach real output to a public
issue. Replace identifiers first, as the issue template describes.
