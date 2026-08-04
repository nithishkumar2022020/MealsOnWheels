# UI Documentation — Index

**Start here.** This folder is the complete handoff for the Flutter app: what to build, in what order, how to wire it to the backend, and what's blocked.

---

## Reading order

1. **[01_UI_BUILD_PLAN.md](./01_UI_BUILD_PLAN.md)** — stages, next action, decisions, deferred items. The single source of truth for progress.
2. **[02_SCREEN_INVENTORY.md](./02_SCREEN_INVENTORY.md)** — all 63 Stitch screens, deduplicated to 57 distinct. Which is canonical, which is blocked, which endpoint feeds it.
3. **[03_DESIGN_TOKENS.md](./03_DESIGN_TOKENS.md)** — the resolved crimson palette, verified contrast, type scale, spacing, radius. Supersedes `../06_DESIGN_SYSTEM.md` on colour/type.
4. **[04_FLUTTER_ARCHITECTURE.md](./04_FLUTTER_ARCHITECTURE.md)** — project structure, Riverpod, dio, error handling, money parsing, routing, testing.
5. **[05_SCREEN_API_WIRING.md](./05_SCREEN_API_WIRING.md)** — per-screen: endpoint, request, response, every error code, empty/loading state.
6. **[06_FULFILMENT_MODES.md](./06_FULFILMENT_MODES.md)** — pickup + delivery, what delivery needs that no side has, phasing.
7. **[mockups/](./mockups/)** — 63 screen PNGs + HTML, plus two Stitch theme specs. Read `mockups/README.md` first.

---

## Status

**Phase:** C — UI scaffold. No Flutter code exists.  
**Next:** Stage 1 — `flutter create`, apply crimson theme, set up dio + Riverpod.  
**Decisions finalized:** crimson palette, dual-font, four fulfilment modes (pickup + delivery), price never sent client→server, money as `Decimal`.

---

## Related

- [../14_BUILD_PLAN.md](../14_BUILD_PLAN.md) — backend progress (Stages 7–10 done, 11–13 next)
- [../FRONTEND_CONTRACT.md](../FRONTEND_CONTRACT.md) — verified API shapes against a running backend
- [../16_FUNCTIONAL_PRODUCT_DATA.md](../16_FUNCTIONAL_PRODUCT_DATA.md) — owner-managed menus/hours, needs sign-off
- [../15_DESIGN_BACKEND_ALIGNMENT.md](../15_DESIGN_BACKEND_ALIGNMENT.md) — where design & backend diverge
