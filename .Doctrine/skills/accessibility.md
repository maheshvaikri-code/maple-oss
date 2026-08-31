# Skill: Accessibility

**Scope.** Every surface operable by everyone — keyboard, screen reader,
low vision, motion sensitivity — web, TUI, and CLI. Deepens `skills/ui.md`.

## Principles
- WCAG 2.2 AA is the floor, not the target.
- Semantic HTML first; ARIA only where semantics don't exist. No ARIA
  beats bad ARIA — a wrong role misleads worse than silence.
- Everything reachable by keyboard: complete path, visible focus, logical
  order, no traps. If the mouse is required, the feature is broken.
- Each of the five states in `skills/ui.md` (empty, loading, partial,
  error, success) must be perceivable without sight or pointer.
- A11y is verified by using, not by scanning.

## Defaults
- Contrast: 4.5:1 for text; 3:1 for large text, UI components, and focus
  indicators.
- Forms: every input has a programmatic label; errors associated with
  their field (`aria-describedby`) and announced via live region — not
  merely painted red.
- Media: captions for video, transcripts for audio, alt text that says
  what the image does; `alt=""` when decorative.
- Motion: respect `prefers-reduced-motion`; nothing essential conveyed
  only by animation.
- Touch targets ≥44px; focus indicators never removed without an equally
  visible replacement.
- CLI/TUI: honor `NO_COLOR`; meaning never carried by color alone; output
  linear and screen-reader-friendly — no status by ASCII art alone.

## Do
- Walk the whole flow keyboard-only, then again with a screen reader
  (NVDA/VoiceOver), before calling it done. Automated tools (axe) catch
  roughly a third of issues; the two manual passes catch the rest.
- Manage focus on route and dialog changes: move it somewhere sensible on
  open, return it on close.
- Use headings and landmarks as a real outline; screen-reader users
  navigate by them.
- Announce async outcomes (saved, failed, loaded) through live regions.

## Don't
- Don't attach click handlers to divs; use buttons and links.
- Don't use placeholder text as the label.
- Don't let focus escape an open modal — or fail to restore it after.
- Don't set `outline: none` and walk away.
- Don't ship an axe-clean page that nobody has operated eyes-free.

## Review checklist
- [ ] Keyboard-only pass done: complete path, visible focus, no traps
- [ ] Screen reader pass done; five states perceivable
- [ ] Contrast verified: 4.5:1 text, 3:1 large text + UI
- [ ] Forms: labels programmatic, errors associated and announced
- [ ] Reduced-motion respected; targets ≥44px; media alternatives present
- [ ] CLI/TUI: `NO_COLOR` honored, no meaning by color alone

## Common failure modes
Div-buttons with perfect styling and zero semantics; ARIA sprayed on to
silence the scanner; the modal you can tab out of but never back into; a
passing axe score on a flow no keyboard has ever completed; the red
border that is the entire error message.
