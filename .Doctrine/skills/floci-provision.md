---
name: floci-provision
description: Provision local emulated cloud infrastructure from a floci.manifest.yaml. Use this whenever a .Doctrine FDE project enters phase P3, whenever a floci.manifest.yaml exists but endpoints.lock.json does not, or whenever the user asks to "stand up", "spin up", or "provision" infrastructure for a prototype — even if they say "AWS", "GCP", or "Azure", because in the prototype phase all clouds are emulated by Floci.
version: 0.1.0
inputs: [floci.manifest.yaml]
outputs: [endpoints.lock.json, .env.floci, logs/provision.log]
---

# floci-provision

Turns the declarative manifest into running emulated services and two contract files the
rest of the pipeline binds to. Code never learns hostnames from anywhere except
`.env.floci`.

## Procedure

1. **Validate** the manifest (required keys, port uniqueness, archetype recognized).
   Invalid → stop with the failing key path; never partially provision.
2. **Pin check.** Compare `floci.version` in the manifest to the installed CLI
   (`floci --version`). Mismatch → stop; version drift breaks determinism and invalidates
   the fidelity table used later by floci-parity.
3. **Up.** `floci up -f floci.manifest.yaml` (bind to your installed Floci CLI syntax).
4. **Health poll** every declared service until green or 60s timeout per service.
5. **Emit `endpoints.lock.json`** — canonical JSON: for each service `{name, kind,
   endpoint, port}` plus `{floci_version, manifest_sha256}`.
6. **Emit `.env.floci`** — one `UPPER_SNAKE` var per service endpoint, sorted, LF.
7. **Log** all CLI output to `logs/provision.log`.

## Determinism requirements

Ports are fixed and declared in the manifest — never ephemeral. Re-running from clean
state MUST produce a byte-identical `endpoints.lock.json` (this is the P3 gate). The lock
file's sha256 is the provision fingerprint referenced by later artifacts.

## Failure modes

- **Port conflict:** stop and report the conflicting host process. Do not silently
  reassign — a moved port is a determinism break; the human either frees the port or
  edits the manifest.
- **Partial up / failed health:** `floci down` full teardown, then report. Never retry
  on top of a partial state.
- **Unknown service kind:** stop; the manifest is ahead of the installed Floci version.
