# Autopilot Log

Decisions made autonomously while the user was away. One line each, newest section
at the bottom. Review the `NEEDS YOUR EYES` section first.

---

## NEEDS YOUR EYES

**0. Design vs backend — mostly aligned, five real gaps.** Review in
`docs/15_DESIGN_BACKEND_ALIGNMENT.md`.

They agree on the product. The one finding that changes the build order: the design has
`booking_type` (bus boarding point / self-drive dine / self-drive takeaway) and the backend
has a single fulfilment mode. Those are three different products sharing an order flow —
different prep timing, different dashboard urgency, different cancellation risk — and it
changes the `bookings` table, so it should land before bookings are built, which is next.

The backend is right on four points and the design should be amended: client-supplied item
prices, the flat 30-minute cutoff, HTTP 500 on an Overpass outage, and `refund_amount` on a
pay-on-arrival cancellation.

**1. Commit authorship.** `git config user.name` / `user.email` were unset in this
repository, which blocks every commit — and you asked for the work to be pushed. Rather
than guess your email (a wrong guess is baked into history permanently), I set a
**repo-local** identity:

```
user.name  = Claude (autopilot)
user.email = noreply@anthropic.com
```

This is local to this clone only — your global git config is untouched. To re-author the
commits under your own name:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
git rebase --root --exec 'git commit --amend --no-edit --reset-author'
```

**2. Nothing has been pushed to `main`.** Work is on branch
`autopilot/backend-build-20260730`, pushed to origin. Merging to `main` is left to you,
per the autopilot rules. No PR opened.

**3. `backend/.env` exists locally and is gitignored.** Verified excluded before the first
commit — `git check-ignore` confirms it. It holds only development placeholders, but do not
force-add it.

---

## Decisions

### Session start — 2026-07-30

- Created branch `autopilot/backend-build-20260730` off `main`; will not switch back to
  `main` for the rest of the session.
- Wrote `.claude/settings.local.json` with `bypassPermissions` plus the destructive
  deny-list (force-push, push to main, hard reset, rm -rf, etc.).
- Set repo-local git identity so commits are possible at all — see NEEDS YOUR EYES above.
- Split the existing uncommitted work into logical commits rather than one `wip:` blob:
  the doc corrections and the backend skeleton are separate concerns and should be
  separately revertable.
- Pushing only the feature branch to `origin`. `git push origin main` is on the deny-list
  and the autopilot rules reserve merge decisions for you.

### 2026-07-31 — frontend contract audit

- Audited the live code (OpenAPI + `app/schemas.py`) rather than the spec docs, since the
  question was whether the *backend* matches the frontend, not whether the docs do.
- Wrote `docs/15_FRONTEND_CONTRACT_AUDIT.md`; linked from `docs/README.md`.
- Marked the spec conflict `BLOCKED` rather than guessing: reversing the cutoff formula or
  the rating definition after bookings ship means rewriting three stages, so a wrong
  autonomous guess is more expensive than waiting.
- Did **not** start renaming fields toward the frontend contract. The rename is cheap
  (~half a day, 0% → ~90% on what exists) but pointless before the Group C answers land,
  and it would have reverted the `arrival_time` rename without you seeing why.
- Verified before committing: 122 tests pass, ruff and black clean.

### 2026-07-31 (later) — reframed the review

- Owner clarified the design spec was a direction check, not an implementation contract.
  The first version audited it as a contract and reported "0% compliance", which measured
  whether field names matched rather than whether the two were heading the same place.
  Rewrote as a judgment call per divergence; renamed the file to match.
- Changed the recommendation on ratings after thinking it through properly: the design's
  hygiene-only headline is good product thinking for highway food, where the anxiety is
  illness rather than taste. Keep all three scores, show hygiene first, expose the
  composite alongside — rather than picking one.
- Same for the error envelope: `message` (displayable) and `code` (branchable) are not
  substitutes, so emit both rather than choosing.
