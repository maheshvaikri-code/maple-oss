# Project/Task Brief — native run-ID validation correction

**Date:** 2026-08-29 · **Class:** M (bounded correction to existing native
runtime boundaries) · **Roles:** Architect / Backend / QA / Release

## Problem

The native workflow and durable-agent entry points used truthiness to decide
whether to generate a run ID. An explicitly supplied empty ID was therefore
treated as omitted. That behavior is inconsistent with the existing bounded
identifier validators and can make a caller believe it selected an ID when the
runtime silently creates another one.

## Scope

- In: `Workflow.run`, durable `AutonomousAgent` sync/async start paths, focused
  regressions, API/release documentation, and local evidence.
- Out: public signature changes, server/client transport, resume semantics,
  remote routing, scheduling, execution, dependencies, publication, and the
  website.

## Acceptance criteria

1. Omitting `run_id` (`None`) retains generated-ID behavior.
2. Explicit empty IDs reach the existing validator and fail before checkpoint,
   session, provider, or tool work.
3. Sync and async durable-agent starts preserve the stable run-store error
   envelope while exposing the validator cause.
4. Existing workflow/run tests, format/lint/type/compile/security checks, and
   clean package smoke remain green.

## Decision gate

This is a correction of an existing validation contract, not a new public
surface. It requires no human escalation under the Doctrine §5 public-API gate.
The authenticated session routes in Slice 202 remain separately gated because
they add routes, scopes, and session-content exposure.

**Status:** implementation in progress; evidence is filed after verification.
