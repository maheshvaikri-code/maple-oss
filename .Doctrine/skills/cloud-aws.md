# Skill: Cloud — AWS (local-first via floci)

Develop and verify AWS-backed projects entirely on the local machine using
the floci emulator (floci.io/aws), then elevate to real AWS as a **pure
configuration change**. Activates at the cloud stage (see routing table)
when the recorded provider preference is `aws`.

## Core principle: one-variable difference

The entire local/cloud split lives in `AWS_ENDPOINT_URL`
(local: `http://localhost:4566`; cloud: unset). Application code never
knows which environment it runs in.

## Hard rules

- NEVER write `if local:` / env-sniffing branches around cloud calls. If
  tempted, the client factory is wrong — fix the factory.
- ALL cloud clients come from **one factory module** (`config/clients.py`
  or Rust equivalent). Grep for stray `boto3.client(` / `Client::new` and
  refactor into it.
- NEVER mock AWS SDKs in integration tests — the emulator encodes the API
  contract; mocks encode your assumptions. Unit tests may still mock.
- Resource names (queues, buckets, tables, topics) are defined **once** in
  the bootstrap script, consumed everywhere via env vars. Never hardcoded.

## Workflow

1. **Scaffold** — `docker-compose.yml` (floci + bootstrap container),
   `scripts/create-resources.sh`, `config/clients.py`, `env.local` /
   `env.cloud` (identical keys, different values). `FLOCI_PERSIST=1` so
   state survives restarts like a real account; reset =
   `docker compose down -v && docker compose up -d`.
2. **Run** — `docker compose up -d`; verify bootstrap logs;
   `curl -sf http://localhost:4566/_floci/health`.
3. **New cloud dependency** = 4 touches: add service to `FLOCI_SERVICES`
   in compose → provision in bootstrap → name into BOTH env files →
   consume via factory.
4. **Test** — integration suite runs against the emulator and must be
   written to run **unmodified** against real AWS.
5. **Elevate** (escalation: paid service — human go required) — source
   `env.cloud`, rerun the same suite, produce a parity report (GO/NO-GO)
   in `docs/qa/`.

## Known emulation gaps (expect these to surprise you in real AWS)

IAM denials, real network latency, and quota/throttling behavior are not
reproduced locally. Note them explicitly in the parity report.

Heavy services (RDS, ElastiCache, MSK, EKS) launch real engines in sibling
containers and need the Docker socket mount — remove the mount if unused.
Verify current service coverage at floci.io/aws before promising a service.
