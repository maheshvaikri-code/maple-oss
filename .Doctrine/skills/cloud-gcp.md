# Skill: Cloud — GCP (local-first via floci-gcp)

Develop and verify GCP-backed projects locally using floci-gcp
(floci.io/gcp), then elevate to real GCP as a configuration change.
Activates at the cloud stage when the recorded provider preference is
`gcp`.

## Core principle: per-service emulator hosts

GCP SDKs honor emulator overrides via env vars per service —
`PUBSUB_EMULATOR_HOST`, `FIRESTORE_EMULATOR_HOST`, `SPANNER_EMULATOR_HOST`,
`STORAGE_EMULATOR_HOST` — or an explicit `api_endpoint` client option.
All such wiring lives in the client factory + env files, never inline.

## Hard rules (shared with all cloud skills)

- No environment-sniffing branches; the factory decides from env vars.
- One client factory; grep for stray `pubsub_v1.PublisherClient(` /
  `storage.Client(` construction outside it and refactor.
- No SDK mocks in integration tests.
- Resource names (topics, subscriptions, buckets, collections) defined
  once in bootstrap; identical env keys in `env.local` / `env.cloud`.
- Local runs use **anonymous credentials** — the factory must supply them
  when an emulator host is set, so no ADC/service-account file is needed
  locally and no credential file is ever committed.

## Workflow

1. Scaffold compose + bootstrap + factory + both env files.
2. `docker compose up -d`; verify bootstrap output.
3. New GCP dependency = compose → bootstrap → both env files → factory,
   plus its `*_EMULATOR_HOST` entry in `env.local` (unset in `env.cloud`).
4. Integration tests target the emulator, written to run unmodified
   against real GCP with ADC.
5. Elevation (human go required — paid): unset emulator hosts, use real
   project ID + ADC, rerun suite, GO/NO-GO parity report in `docs/qa/`.

## Honest caveats

Verify service coverage at floci.io/gcp first. IAM policy denials, quota
behavior, and real latency are not emulated; per-service emulator hosts
mean a missing env var silently sends traffic to REAL GCP — the factory
should hard-fail if `ENV=local` and an expected emulator host is unset.
