# Skill: UI (web, TUI, and CLI ergonomics)

**Scope.** Anything a human perceives and operates: web frontends, terminal
UIs, CLI surfaces, and the error text of all three.

## Principles
- Design states before visuals. Every surface has five: empty, loading,
  partial, error, success. Unhandled states are the top source of "feels broken."
- The interface teaches itself: sensible defaults, progressive disclosure,
  consistent vocabulary across screens/commands.
- Latency honesty: show progress for anything >400ms; never fake a spinner
  over an operation that already failed.
- Accessibility is a requirement, not polish.

## Defaults
- Web: semantic HTML first; components small and typed; state minimal and
  local; design tokens over magic values; system fonts unless there's a reason.
- CLI: `tool <noun> <verb>` or `tool <verb>` — pick one grammar and keep it;
  `--help` on every level with examples; exit 0 = success, distinct codes
  per failure class; human output to stdout, diagnostics to stderr;
  `--json` where the output is data; respect `NO_COLOR` and non-TTY pipes.
- Copy: sentence case, active voice, no blame ("Couldn't save — disk full.
  Free space and retry." not "Error 5023").

## Do
- Walk the keyboard-only path personally before calling a view done.
- Make destructive actions confirm with specifics ("delete 14 files?"), and
  prefer undo over confirmation where feasible.
- Keep forms/flags forgiving: trim whitespace, accept obvious formats,
  validate early with messages next to the problem.
- Test the empty state with a genuinely new user's data: nothing.

## Don't
- Don't ship a view whose error state has never been rendered.
- Don't use color as the only signal for anything.
- Don't print secrets, tokens, or full paths in UI/CLI errors.
- Don't add configuration for what a good default would solve.
- Don't animate anything that happens more than once a minute.

## Review checklist
- [ ] Five states implemented and reachable per surface
- [ ] Keyboard/no-color/non-TTY paths verified
- [ ] Error copy: what happened, why, next step
- [ ] Vocabulary consistent with the rest of the product
- [ ] Destructive paths confirm-or-undo

## Common failure modes
Happy-path demos; spinner-forever on failure; helpful GUI + hostile CLI in
the same product; a11y retrofits that never come.
