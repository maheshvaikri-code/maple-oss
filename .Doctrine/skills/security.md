# Skill: Security

**Scope.** Secrets, input trust boundaries, dependency hygiene, dangerous
constructs, and failure posture — for applications and libraries alike.

## Principles
- Trust is directional and explicit: draw the boundary; everything crossing
  inward is hostile until parsed and bounded.
- Fail closed: an error in an authorization or validation path denies.
- Least privilege everywhere: tokens, file modes, CI permissions, DB users.
- Secrets have one home (env/secret store) and zero copies in code, logs,
  errors, fixtures, or history.

## The standing audit (run at G5 and on touch)
1. **Secrets:** scan diff + outgoing history (`gitleaks` or equivalent);
   grep error/log paths for token-shaped leakage.
2. **Injection:** SQL (parameterized only), shell (no string-built
   commands; use exec arrays), path (canonicalize + prefix-check),
   template/HTML (encode on output). Any identifier that becomes part of
   a path — including ids from your OWN state/config files — is a trust
   boundary: charset-constrain at parse AND resolve()+prefix-check at use.
3. **Deserialization:** no `pickle`/`eval`/`exec` on untrusted data;
   `yaml.safe_load`; JSON parsed with size/depth bounds.
4. **Dependencies:** `cargo audit` / `pip-audit` / `npm audit` — run,
   attach output, disposition findings in writing.
5. **Dangerous constructs:** Rust `unsafe` (must carry `// SAFETY:` +
   review), disabled TLS verification, world-writable files, temp-file
   races (use the stdlib tempfile primitives), `subprocess(shell=True)`.
6. **Resource bounds:** sizes, depths, counts, timeouts on everything
   user-influenced (zip bombs, billion-laughs, unbounded regex).
7. **Agent-context emission:** anything written into files agents
   auto-read (AGENTS.md, CLAUDE.md, rules files, hydration bundles) is
   an injection surface — model-authored text is untrusted input to
   future sessions. Validate fence/marker integrity strictly and
   reject/neutralize markup tokens in emitted bodies, fail-closed.

## Defaults
- Constant-time comparison for secrets; passwords only via a modern KDF
  (argon2/bcrypt/scrypt) — never rolled by hand.
- OS RNG / vetted crypto libraries only; no homemade crypto, ever.
- Error messages to users are generic; details go to logs with correlation
  IDs — and logs still never contain secrets or full payloads with PII.
- Library code documents its trust assumptions ("callers must validate X").

## Do
- Threat-sketch each L-class feature in three lines: assets, entry points,
  worst plausible abuse. It changes designs early and cheaply.
- Rotate anything that leaks immediately; a secret that touched a commit is
  burned even if the commit never pushed.
- Keep authz checks at the moment of action (not only at login), and test
  the denied paths.

## Don't
- Don't log tokens, passwords, or full request bodies.
- Don't accept "it's internal" as a trust argument.
- Don't vendor/copy crypto or auth code from answers you can't verify.
- Don't disable a security check to make a test pass.
- Don't treat the audit as ceremony — findings without disposition are
  worse than not looking.

## Review checklist
- [ ] Secrets scan clean; no token-shaped strings in logs/errors
- [ ] Injection review per new input path, with the encoding at output
- [ ] Dep audit output attached; findings dispositioned
- [ ] `unsafe`/dangerous constructs justified or gone
- [ ] Bounds + timeouts on user-influenced resources; fail-closed verified

## Common failure modes
The .env that made it into history; string-formatted SQL "just for this
internal tool"; audit step green because it never ran; unbounded upload
that met a 2GB "hello".
