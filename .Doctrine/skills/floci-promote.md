---
name: floci-promote
description: Emit the real-cloud promotion artifacts (IaC diff, endpoint mapping, checklist) for a verified prototype. Use this in FDE phase P6 whenever the user asks to "deploy", "promote", "move to AWS/GCP/Azure", "productionize", or "hand off" a Floci-backed prototype. This skill EMITS artifacts only — it never applies IaC or calls real cloud APIs, and it refuses to run without a valid parity-ledger.json.
version: 0.1.0
inputs: [floci.manifest.yaml, parity-ledger.json (required), endpoints.lock.json]
outputs: [iac-diff/, env-mapping.md, PROMOTION.md]
---

# floci-promote

Promotion is a config swap, not a rebuild — but only because everything upstream enforced
it. This skill turns the manifest + ledger into artifacts a human reviews and applies.

## Hard rules

1. **Ledger required.** No `parity-ledger.json`, or `summary.gate == "block"` → refuse
   and point to floci-parity. There is no override flag.
2. **Emit-only.** Never execute `terraform apply`, `aws`, `gcloud`, `az`, or any real
   cloud CLI. Generated IaC is reviewed and applied by a human.
3. **No invented values.** Account ids, regions, VPC ids, and quotas render as explicit
   `TODO(owner)` placeholders — never plausible-looking defaults.

## Procedure

1. Read `promotion_target` from the manifest (`aws|gcp|azure`). `undecided` → stop and
   ask; do not emit three speculative diffs.
2. **`iac-diff/`** — Terraform skeleton mapping each manifest service to its real
   counterpart on the target cloud (bucket → S3/GCS/Blob, queue → SQS/PubSub/Storage
   Queue, function → Lambda/Cloud Functions/Azure Functions, vector store → the target's
   managed option or a `TODO(choice)` block when the target offers several).
3. **`env-mapping.md`** — table: every `.env.floci` variable → the real endpoint/ARN
   expression that replaces it. This file is the literal "config swap".
4. **`PROMOTION.md`** — ordered checklist: prerequisites (account, IAM roles as TODOs),
   apply steps, smoke test (the same demo scenario, now against real endpoints, expected
   to reproduce the demo's observable output), and rollback note. Then **one checklist
   line per `partial` or `stub` ledger entry**, naming the operation and the specific
   divergence to re-verify on the real cloud. Ledger entries are the checklist's source
   of truth — no entry may be dropped or merged.
5. Stamp all three artifacts with `manifest_sha256` and the ledger's sha256 so a stale
   promotion pack is detectable.

## Failure modes

- **Ledger/manifest hash mismatch** (manifest edited after verification): stop; re-run
  P5 first.
- **Unmappable service** on the target cloud: emit the rest, and record the gap as a
  blocking checklist item rather than inventing a mapping.
