# Autopilot Log

Decisions made autonomously while the user was away. One line each, newest section
at the bottom. Review the `NEEDS YOUR EYES` section first.

---

## NEEDS YOUR EYES

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
