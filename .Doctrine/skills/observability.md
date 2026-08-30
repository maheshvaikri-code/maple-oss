# Skill: Observability

**Scope.** Logging, metrics, and diagnostics — the ability to explain, at
3 a.m., what the system did and why, from artifacts it left behind.

## Principles
- Logs are for the operator debugging without you present. Every event
  answers: what happened, to what, and with which identifiers to correlate.
- Structure beats prose: key-value/JSON logs machine-filterable; message
  text stable enough to grep and alert on.
- Levels mean things: ERROR = broken, act · WARN = degraded/surprising,
  investigate · INFO = state changes at boundaries · DEBUG = development
  detail, off by default. Level inflation makes everything noise.
- Never log secrets, tokens, passwords, or whole payloads containing PII.
  This outranks debuggability, always.

## Defaults
- Rust: `tracing` with spans at operation boundaries; `tracing-subscriber`
  env-filtered; libraries emit events, binaries choose subscribers.
- Python: stdlib `logging` with a module-level logger per file
  (`logging.getLogger(__name__)`); no `print` in library code; structured
  formatter at the app edge; libraries never call `basicConfig`.
- Correlation/request IDs generated at the entry boundary and threaded
  through every log line and outbound call for that operation.
- Errors logged once, at the level that handles them, with context —
  not at every frame they pass through.

## Do
- Log boundary events: request in/out (with duration), external call
  results, job start/finish, state transitions — with IDs, not payloads.
- Count what matters for long-running things: operations, failures,
  durations, queue depths — even a periodic stats log line beats nothing.
- Ship health/readiness signals for anything that runs unattended; make
  `--verbose`/`RUST_LOG`/`LOG_LEVEL` do what people expect.
- When a bug is fixed, ask "what log line would have found this in one
  grep?" — add it.

## Don't
- Don't log in tight loops without sampling/rate-limiting.
- Don't interpolate user input raw into log messages (log-forging, PII);
  put it in fields, bounded.
- Don't leave DEBUG-level firehoses or leftover `dbg!`/`print` in merged code.
- Don't build a metrics cathedral for a CLI — proportionality: a `-v` flag
  and clean stderr may be the whole story.

## Review checklist
- [ ] Boundary events logged with correlation IDs and durations
- [ ] Levels used to spec; no error-spam for handled conditions
- [ ] Secret/PII audit of every new log line
- [ ] Failure diagnostics sufficient: could you debug this from logs alone?
- [ ] Debug leftovers removed; verbosity controls documented

## Common failure modes
Silent failure paths (the error goes nowhere); ERROR-level heartbeat noise
training everyone to ignore ERROR; the token in the log that made the
incident a breach; logs so unstructured that grep is archaeology.
