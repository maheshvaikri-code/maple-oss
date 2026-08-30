# Skill: Mobile

**Scope.** iOS, Android, and cross-platform apps — lifecycle, offline
behavior, release trains, store constraints, and the device fleet at large.

## Principles
- The network is a sometimes-thing. Offline-first where the product
  allows, offline-honest where it doesn't. Writes queue and sync; user
  input never dies in a dead spot.
- The lifecycle is hostile: the OS kills the process at any moment.
  State restoration is a tested path, not a hope.
- Battery, memory, and binary size budgets are features; users feel
  drain and jank long before they notice your roadmap.
- Platform conventions win — HIG on iOS, Material on Android. A
  cross-platform UI that feels alien on both is two bad apps in one.
- You can't hotfix. Release trains plus store review latency put weeks
  between fix and fleet; feature flags and remote kill switches decouple
  ship from release.
- Old clients live for years. API changes stay backward-compatible; the
  server tolerates every version still in the wild.

## Defaults
- Crash reporting with symbol/mapping upload from day one — an
  unsymbolicated crash is a rumor, not a report.
- Permissions: ask late, ask in context, one at a time; every denial has
  a graceful degradation path.
- Deep links and notifications are entry points — designed and tested as
  first-class flows, including cold start and killed state.
- A real device matrix that mirrors the install base: old OS versions,
  low-end hardware, small screens — not just the newest simulator.
- UI follows `skills/ui.md`; API compatibility follows
  `standards/api-design.md`.

## Do
- Persist user input at the moment of entry (drafts, form state); assume
  process death at any keystroke.
- Exercise death-and-restore in tests for every screen that holds state.
- Track startup time, jank, and binary size in CI with budgets that fail
  the build when breached.
- Put a kill switch on every feature that talks to your backend.

## Don't
- Don't block the UI thread with I/O; jank is a defect, not ambience.
- Don't assume "online" means fast — test on slow, flaky networks.
- Don't remove or repurpose an API field while any shipped client still
  reads it; that outage can't be patched, only waited out.
- Don't stack permission prompts at first launch.
- Don't treat push notifications as guaranteed delivery.

## Review checklist
- [ ] Writes survive offline: queued, synced, conflict story stated
- [ ] Process-death restoration tested for every changed screen
- [ ] New remote-facing features behind a flag or kill switch
- [ ] API change tolerated by every client version still in the wild
- [ ] Permissions asked in context; denial degrades gracefully
- [ ] Deep link and notification entries tested, cold start included

## Common failure modes
Form input lost to a background kill; the "small" API change that bricked
year-old clients; a permission stampede at first launch tanking opt-in
rates; the bug with no kill switch spending two weeks in store review;
green on the newest simulator, broken on the low-end phones the actual
install base carries.
