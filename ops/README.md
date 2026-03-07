# Ops

This directory contains operational tooling that does not belong in the project root.

## Archive

`ops/archive/` holds historical operational helpers that were moved out of the root during cleanup:

- `enrichment_legacy/` for one-off enrichment runners and monitors
- `systemd/` for legacy service and timer units

These files are retained for context, not as current operational guidance. Many are tied to older enrichment workflows and may contain stale endpoints or assumptions.
