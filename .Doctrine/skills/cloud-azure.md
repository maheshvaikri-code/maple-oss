# Skill: Cloud — Azure (local-first via floci-az)

Develop and verify Azure-backed projects locally using floci-az
(floci.io/az), then elevate to real Azure as a configuration change.
Activates at the cloud stage when the recorded provider preference is
`azure`.

## Core principle: one-variable difference

floci-az exposes an **Azurite-compatible connection string on a single
port**. The local/cloud split lives in connection-string / endpoint env
vars (`AZURE_STORAGE_CONNECTION_STRING`, per-service `*_ENDPOINT` vars) —
never in code.

## Hard rules (shared with all cloud skills)

- No environment-sniffing branches around cloud calls — fix the factory.
- One client factory module; grep for stray `BlobServiceClient(`,
  `ServiceBusClient(` etc. outside it and refactor.
- No SDK mocks in integration tests; the emulator is the contract.
- Resource names (containers, queues, topics, tables) defined once in the
  bootstrap script; consumed via env vars from `env.local` / `env.cloud`
  with identical keys.

## Workflow

1. Scaffold compose + bootstrap + factory + both env files (mirror the
   AWS skill's shape; swap SDK and connection-string wiring).
2. `docker compose up -d`; verify bootstrap provisioned every resource.
3. New Azure dependency = the same 4 touches: compose → bootstrap → both
   env files → factory.
4. Integration tests run against floci-az and must run unmodified against
   real Azure.
5. Elevation (human go required — paid): swap to `env.cloud` (real
   connection strings from Key Vault / portal, never committed), rerun the
   suite, file a GO/NO-GO parity report in `docs/qa/`.

## Honest caveats

floci-az coverage is narrower than the AWS side — **verify the service
list at floci.io/az before designing around a service**. Entra ID auth
flows, RBAC denials, and throttling are not emulated; local runs use the
emulator's well-known dev credentials. Flag all of this in the parity
report.
