# Autopilot Log

Decisions made autonomously while the user was away. One line each, newest section
at the bottom. Review the `NEEDS YOUR EYES` section first.

---

## NEEDS YOUR EYES

**0. BLOCKED — the frozen frontend spec and this backend are two different contracts.**
Audit written to `docs/15_FRONTEND_CONTRACT_AUDIT.md`. Wire-format compliance is **0%**: not
one built endpoint matches the design spec field-for-field, and 11 of 16 endpoints do not
exist yet.

I stopped rather than start rewriting, because three of the conflicts are not mine to
resolve — a flat 30-minute cutoff vs per-restaurant prep time, hygiene-only vs composite
rating, and whether `cancel` should return a `refund_amount` when payment is on arrival and
no money was ever taken. Picking wrong on any of those means redoing bookings, dashboard,
and ratings a second time. See §2 of the audit; §9 has the work order once you decide.

Two things I would push back on regardless of the rest: the spec's booking request sends
client-supplied item `price` (lets a caller book two dishes for ₹0.02 — the backend refuses
this deliberately), and it specifies HTTP 500 when Overpass is down (its own checklist
contradicts this two lines later). Everything else in the spec I would adopt as written.

The spec also contradicts itself in four places that need resolving before it can be
implemented at all — most importantly Part 8 mandates a `{data, message, status}` envelope
while all 16 worked examples in Part 2 show bare objects. Details in §3.

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
