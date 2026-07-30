# Agent instructions — MealsOnWheels

## Read this first

1. **[docs/14_BUILD_PLAN.md](./docs/14_BUILD_PLAN.md)** — the single source of truth for
   what is built, what is next, and where the previous agent stopped. Read it before
   touching anything. Update it before you stop.
2. **[docs/README.md](./docs/README.md)** — doc index and reading order.
3. The spec docs relevant to your stage (linked from the build plan).

The spec is authoritative over your instincts. If you disagree with the spec, change the
spec first and record why — do not let code and docs drift apart.

## Working rules

- **One stage at a time, and leave it working.** Every stage in the build plan ends at a
  state that runs and is verified. Never leave a stage half-applied across several
  modules. If you are running out of room, finish the smallest coherent unit, update the
  build plan, and stop.
- **Update the build plan as the last action of every stage.** Mark the stage done, note
  anything you deferred or discovered, and state the exact next step. Assume you will not
  be here to explain it.
- **Verify before claiming done.** Run the thing. `ruff check`, `black --check`, `pytest`,
  and for API work an actual request against a running server. If it did not run, say so.
- **No scope creep.** Build what the stage says. New ideas go into the build plan's
  Deferred section, not into this commit.

## Conventions (do not rediscover these)

- Python: `black` line length 100, `ruff`, type hints on every signature, `async def` for
  route handlers and DB access.
- Routers stay thin — logic belongs in `app/services/`. Never return a raw SQLAlchemy
  model; always map through a Pydantic schema.
- API: `/api` prefix, JSON only, errors as `{"detail": "...", "code": "..."}`.
- Timestamps `TIMESTAMPTZ`, always UTC. Phones E.164. PostGIS points
  `GEOGRAPHY(POINT, 4326)`.
- Commits: `<type>(<scope>): <description>` — types `feat|fix|docs|chore|refactor|test`,
  scopes `backend|mobile|dashboard|infra|docs`.

## Repository state

Work happens on `autopilot/backend-build-20260730`, not `main`. Merging is the owner's call.

A **repo-local** git identity (`Claude (autopilot)` / `noreply@anthropic.com`) was set so
commits are possible at all; the owner's global config is untouched. See
[AUTOPILOT_LOG.md](./AUTOPILOT_LOG.md) for how to re-author under a real name. Do not change
this identity yourself.

## Security constraints

Not negotiable, regardless of convenience:

- The OTP stub and the shared restaurant dashboard token are **gated to
  `ENVIRONMENT != production`**. Do not remove the gate.
- Item prices are **never** trusted from the client. The server validates every line item
  against its own menu and computes the total itself.
- `/docs` and `/redoc` are disabled when `ENVIRONMENT == production`.
- Never commit secrets. `.env` is gitignored; `.env.example` holds placeholders only.
- Never log a phone number unmasked, or a JWT at all.
