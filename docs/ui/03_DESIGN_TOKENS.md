# Design Tokens — Vibrant Transit

**Status:** authoritative for the Flutter app.
**Supersedes:** the colour and typography tables in
[../06_DESIGN_SYSTEM.md](../06_DESIGN_SYSTEM.md) §2 and §3.
**Source:** `mockups/vibrant_transit/DESIGN.md` — Stitch's own theme spec, chosen by the
owner on 2026-08-01 over the teal alternative.

Everything else in `06_DESIGN_SYSTEM.md` — the philosophy, spacing intent, iconography,
motion, map styling — still stands. Only colour and type are replaced, because the mockups
disagreed with it and the mockups are what the owner approved.

---

## 1. Why this file exists

The 63 mockups were generated across several sessions and drifted: two palettes, two font
pairings, two currencies, three product names. That is normal for exploration and fatal in
an app, where a theme is a single object. This file is the resolution. **Take colours from
here, not from a screen's HTML** — a given `code.html` may hold either palette.

---

## 2. Colour

Material 3 token set. `primary` is "Hunger Red": high-chroma, appetite-stimulating, and the
one colour a traveller must find on a bright dashboard at 60 km/h.

### 2.1 Core

| Token | Hex | Use |
|-------|-----|-----|
| `primary` | `#b7122a` | Primary buttons, prices, critical status |
| `on-primary` | `#ffffff` | Text/icons on primary |
| `primary-container` | `#db313f` | Tonal fills, selected chips |
| `on-primary-container` | `#fffbff` | Text on primary-container |
| `inverse-primary` | `#ffb3b1` | Primary on dark surfaces |
| `secondary` | `#5f5e5e` | "Road Grey" — headers, body grounding |
| `on-secondary` | `#ffffff` | |
| `secondary-container` | `#e4e2e1` | Inactive chips, subtle fills |
| `on-secondary-container` | `#656464` | |
| `tertiary` | `#805200` | Amber accent — "cooking" status |
| `on-tertiary` | `#ffffff` | |
| `tertiary-container` | `#a06900` | |
| `on-tertiary-container` | `#fffbff` | |
| `error` | `#ba1a1a` | Validation, cancelled, destructive |
| `on-error` | `#ffffff` | |
| `error-container` | `#ffdad6` | Error banners |
| `on-error-container` | `#93000a` | |

### 2.2 Surfaces

| Token | Hex |
|-------|-----|
| `surface` / `background` | `#f9f9f9` |
| `surface-container-lowest` | `#ffffff` |
| `surface-container-low` | `#f3f3f3` |
| `surface-container` | `#eeeeee` |
| `surface-container-high` | `#e8e8e8` |
| `surface-container-highest` | `#e2e2e2` |
| `surface-dim` | `#dadada` |
| `surface-variant` | `#e2e2e2` |
| `on-surface` / `on-background` | `#1a1c1c` |
| `on-surface-variant` | `#5b403f` |
| `inverse-surface` | `#2f3131` |
| `inverse-on-surface` | `#f1f1f1` |
| `outline` | `#8f6f6e` |
| `outline-variant` | `#e4bebc` |
| `surface-tint` | `#bb162c` |

### 2.3 Fixed tokens

Used where a colour must not shift between light and dark mode — status pills that mean the
same thing in both.

| Token | Hex | | Token | Hex |
|---|---|---|---|---|
| `primary-fixed` | `#ffdad8` | | `secondary-fixed` | `#e4e2e1` |
| `primary-fixed-dim` | `#ffb3b1` | | `secondary-fixed-dim` | `#c8c6c6` |
| `on-primary-fixed` | `#410007` | | `on-secondary-fixed` | `#1b1c1c` |
| `on-primary-fixed-variant` | `#92001c` | | `on-secondary-fixed-variant` | `#474747` |
| `tertiary-fixed` | `#ffddb4` | | `tertiary-fixed-dim` | `#ffb954` |
| `on-tertiary-fixed` | `#291800` | | `on-tertiary-fixed-variant` | `#633f00` |

### 2.4 Verified contrast

Computed with the WCAG 2.1 relative-luminance formula, not estimated:

| Pair | Ratio | Verdict |
|------|-------|---------|
| `on-surface` on `surface` | **16.26** | AA / AAA |
| `on-surface-variant` on `surface` | **8.87** | AA / AAA |
| `white` on `primary` | **6.70** | AA |
| `primary` on `background` | **6.37** | AA |
| `secondary` on `background` | **6.14** | AA |
| `error` on `background` | **6.14** | AA |
| `white` on `primary-container` | **4.64** | AA (body) |
| `outline` on `background` | **4.27** | **Large text / non-text only** |

**`outline` fails AA for body text.** Use it for borders, dividers, and disabled iconography
— never for a label a traveller has to read. Use `on-surface-variant` (8.87) instead.

Re-run after any palette change:

```bash
python3 -c "
def lum(h):
    h=h.lstrip('#'); c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]
def cr(a,b):
    l1,l2=sorted([lum(a),lum(b)],reverse=True); return (l1+0.05)/(l2+0.05)
print(round(cr('#ffffff','#b7122a'),2))"
```

### 2.5 Order status colours

The five backend statuses (`pending`, `confirmed`, `ready`, `handed_over`, `cancelled`) are
fixed — see [05_SCREEN_API_WIRING.md](./05_SCREEN_API_WIRING.md). Mockup labels differ from
enum values; map deliberately.

| Status | Display | Token | Icon |
|--------|---------|-------|------|
| `pending` | "Pending" | `tertiary` on `tertiary-fixed` | `schedule` |
| `confirmed` | "Confirmed" | `primary` on `primary-fixed` | `check_circle` |
| `ready` | "Ready" | `#1e6b4d` on `#d7f0e5` | `room_service` |
| `handed_over` | "Picked up" | `secondary` on `secondary-fixed` | `flag` |
| `cancelled` | "Cancelled" | `error` on `error-container` | `cancel` |

Verified badge contrast: pending **5.20**, confirmed **5.19**, ready **5.35**, picked up
**5.01**, cancelled **7.24**. All AA.

**On "Arrival Green".** The Stitch spec names a success colour for delivered states but
gives no hex, so it had to come from somewhere. `06_DESIGN_SYSTEM.md` `--color-success`
`#2d936c` was the obvious candidate and is what this table said first — but measured against
the `#d7f0e5` tint it scores **3.18**, which fails AA for text. It was darkened to `#1e6b4d`
(5.35). If a designer wants `#2d936c` back, it needs a darker tint behind it or restriction
to non-text use.

---

## 3. Typography

Dual-font by design: **Montserrat** for headlines (geometric, urgent), **Inter** for
everything functional (higher x-height, legible small on a moving bus).

| Token | Family | Size | Weight | Line height | Tracking |
|-------|--------|------|--------|-------------|----------|
| `headline-xl` | Montserrat | 32 | 700 | 40 | −0.02em |
| `headline-lg` | Montserrat | 24 | 700 | 32 | — |
| `headline-lg-mobile` | Montserrat | 20 | 700 | 28 | — |
| `body-lg` | Inter | 18 | 400 | 28 | — |
| `body-md` | Inter | 16 | 400 | 24 | — |
| `label-md` | Inter | 14 | 600 | 20 | +0.01em |
| `label-sm` | Inter | 12 | 500 | 16 | — |

Sizes are deliberately larger than a typical web app to survive a bumpy bus. **Never go
below `label-sm` (12).** Support OS font scaling to 200% without layout break — test the
booking status screen at 200%, it is the densest.

Both families via `google_fonts`. Money and countdowns use tabular figures
(`FontFeature.tabularFigures()`) so a ticking timer does not shift the layout.

---

## 4. Spacing, radius, elevation

**8 px base unit.**

| Token | Value | Use |
|-------|-------|-----|
| `base` | 8 | Tight grouping |
| `gutter` | 16 | Standard gap, card padding |
| `container-margin` | 20 | Screen side margins |
| `section` | 32 | Section breaks |
| `touch-target-min` | **48** | Minimum tap target — non-negotiable |

| Radius | Value | Use |
|--------|-------|-----|
| `sm` | 4 | Badges |
| `DEFAULT` | 8 | Inputs, small buttons |
| `md` | 12 | — |
| `lg` | 16 | Item cards, modal sheets |
| `xl` | 24 | Bottom sheets |
| `full` | 9999 | Status pills, filter chips |

Pill shape is reserved for **badges and chips** so they never read as tappable buttons.

| Elevation | Shadow | Use |
|-----------|--------|-----|
| 1 | `0 4px 20px rgba(0,0,0,0.06)` | Cards |
| 2 | `0 8px 24px rgba(0,0,0,0.10)` | Floating "View Cart" |

On press, cards **reduce** shadow spread — they sink rather than lift.

---

## 5. Non-negotiables

Carried from the backend contract; getting these wrong is a correctness bug, not a taste
issue. Full detail in [../FRONTEND_CONTRACT.md](../FRONTEND_CONTRACT.md).

- **Currency is ₹ INR.** Several mockups show `$`. The backend returns money as a JSON
  **string** (`"80.00"`) to be parsed as `Decimal`, never `double`.
- **An unrated restaurant shows "New", not 0★.** `composite_rating` is `null` until rated,
  and every seeded restaurant is currently unrated.
- **There are no images.** No endpoint returns one. Every `[img]` in the mockups is a
  placeholder — use an icon tile until Phase 2 adds image URLs.
- **Minimum 48 dp touch targets**, primary buttons 56 dp per the Stitch spec.

---

## 6. Dark mode

Phase 2. The Stitch spec names a "Night Road" strategy — `#121212` base, `#1e1e1e` elevated,
primary red retained — but gives no full token set. Structure `AppTheme` with light and dark
`ColorScheme`s from day one so adding it is a table, not a refactor. Ship light only.

---

## 7. Related

- [04_FLUTTER_ARCHITECTURE.md](./04_FLUTTER_ARCHITECTURE.md) — how these become `ThemeData`
- [mockups/vibrant_transit/DESIGN.md](./mockups/vibrant_transit/DESIGN.md) — the source spec
- [../06_DESIGN_SYSTEM.md](../06_DESIGN_SYSTEM.md) — superseded on colour/type only
