# 04 — Live MLflow and Databricks integrations

Status: ready-for-human
Blocked by: None for functional delivery; C4 human validation is separate.
Milestone: C3

Verify installed SDK signatures; implement bounded header pagination and explicit
artifact fetching, configurable paths/session context, provenance cohorts and
completeness diagnostics. Add real taxonomy/evidence calls and independent doctor
probes with bounded retries. See the [specification index](../spec.md).

Acceptance: record separate live evidence for MLflow and model connectivity and
exact SDK versions; visibly handle failed downloads, unsupported shapes, oversized
inputs, auth/service failures, invalid JSON, truncation and temperature rejection.
Test with fake adapters too; do not silently export raw configuration or secrets.

## Comments

- 2026-11-24: Earlier exploratory MLflow access does not prove this implementation.

- 2026-11-24: Functional implementation and verification complete. See ConvoSignal
  milestones for test/build/connectivity evidence; C4 human validation is separate.
