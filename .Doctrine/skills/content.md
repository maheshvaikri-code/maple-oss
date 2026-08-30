# Skill: Content

**Scope.** Posts, release notes, social copy, docs-adjacent writing —
prose that ships the product's truth. Drafts only; the human publishes.

## Principles
- Write from the CHANGELOG outward: the artifact exists first, the story
  second. Never announce what didn't ship.
- Every technical claim is checkable or it doesn't run: claim → shipped
  tag, artifact, or measurement, in a claims table attached to the draft.
- The lede states the user's benefit, not the feature's existence.
  "You can now X" beats "We added X support" in every draft.
- Superlatives require a measurement or die in review. "Fastest" is a
  benchmark citation or it is fiction.
- One reader, one message, one CTA. A post for everyone converts no one.

## Defaults
- Claims table travels with the draft — one row per assertion, evidence
  linked — verified in the human's pre-send review (.Doctrine.md §5).
- Screenshots and terminal outputs are real captures from the shipped
  build, dated; anything staged or simulated is labeled so in-frame.
- Release-note voice: what changed, who it affects, what to do — in that
  order, no adjectives doing load-bearing work.
- Drafts name their one reader at the top (internal note, stripped before
  publish); every paragraph earns its place against that reader.
- Publishing, posting, and scheduling are the human's acts; the skill
  delivers the draft, the claims table, and a suggested slot.

## Do
- Open with the reader's outcome; put the company's effort in paragraph
  three or cut it.
- Quote measurements with fidelity labels intact (`skills/metrics.md`) —
  a number stripped of "estimated" becomes a lie in transit.
- Read the draft against the CHANGELOG line by line before handing it
  over; every feature named must have a shipped reference.
- Cut the second message into its own draft. Two ideas, two posts.

## Don't
- Don't present mockups, renders, or staged data as real product output.
- Don't announce roadmap as release; "coming soon" needs a date the team
  actually committed to, or it stays unwritten.
- Don't bury the CTA under three closing paragraphs; end on it.
- Don't let marketing verbs inflate technical claims — "blazing",
  "seamless", "enterprise-grade" are review flags, not descriptions.
- Don't publish anything yourself, anywhere, ever.

## Review checklist
- [ ] Every technical claim has a claims-table row with live evidence
- [ ] Lede states user benefit; one reader, one message, one CTA
- [ ] Screenshots and outputs are real captures from the shipped build
- [ ] Superlatives measured or removed; fidelity labels intact
- [ ] Nothing announced beyond the CHANGELOG
- [ ] Draft plus claims table queued for the human's pre-send review

## Common failure modes
The announcement that outruns the release; benefit buried under feature
inventory; a mocked screenshot that becomes "the product" in a prospect's
memory; superlative inflation one adjective at a time; three CTAs
cancelling each other; the claims table filled in after the post went
out, which is to say never.
