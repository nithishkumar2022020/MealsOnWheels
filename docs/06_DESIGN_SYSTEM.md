# Design System — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md)

---

## 1. Design Philosophy

MealsOnWheels serves travellers in motion — often in bright sunlight, poor connectivity, and time pressure. The design system prioritizes:

1. **Clarity over decoration** — Large tap targets, high contrast, minimal chrome
2. **Time visibility** — Countdowns and arrival times are first-class UI elements
3. **Map + list parity** — Every list item has a map equivalent
4. **Accessibility by default** — WCAG 2.1 AA contrast ratios, scalable text

Visual tone: **confident highway travel** — warm earth tones, clear status colors, no generic "delivery app" gradients.

---

## 2. Color Tokens

### 2.1 Brand palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-primary` | `#E85D04` | Primary actions, brand accent (highway amber) |
| `--color-primary-dark` | `#C44900` | Pressed/hover primary |
| `--color-secondary` | `#1B4965` | Headers, navigation (deep road blue) |
| `--color-accent` | `#2EC4B6` | Success highlights, map route line |
| `--color-surface` | `#FFFCF7` | Page background (warm white) |
| `--color-surface-elevated` | `#FFFFFF` | Cards, modals |
| `--color-text-primary` | `#1A1A2E` | Body text |
| `--color-text-secondary` | `#5C5C6D` | Captions, metadata |
| `--color-border` | `#E8E4DF` | Dividers, card borders |

### 2.2 Semantic colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-success` | `#2D936C` | Confirmed, ready, handed_over |
| `--color-warning` | `#F4A261` | Approaching cutoff, pending |
| `--color-error` | `#D62828` | Cancelled, errors, validation |
| `--color-info` | `#457B9D` | Informational banners |

### 2.3 Order status colors

| Status | Color token | Icon |
|--------|-------------|------|
| `pending` | `--color-warning` | Clock |
| `confirmed` | `--color-info` | Check circle outline |
| `ready` | `--color-success` | Bell |
| `handed_over` | `--color-secondary` | Flag |
| `cancelled` | `--color-error` | X circle |

---

## 3. Typography

**Font family (Flutter):** `Inter` (bundled via `google_fonts` package)

| Token | Size | Weight | Line height | Usage |
|-------|------|--------|-------------|-------|
| `display-lg` | 32 sp | 700 | 1.2 | Splash, empty states |
| `heading-lg` | 24 sp | 600 | 1.3 | Screen titles |
| `heading-md` | 20 sp | 600 | 1.35 | Section headers |
| `body-lg` | 16 sp | 400 | 1.5 | Primary body |
| `body-md` | 14 sp | 400 | 1.5 | Secondary body |
| `label-lg` | 14 sp | 600 | 1.4 | Buttons, tabs |
| `label-sm` | 12 sp | 500 | 1.4 | Badges, timestamps |
| `mono` | 14 sp | 500 | 1.4 | Booking IDs, countdowns |

**Minimum readable size:** 14 sp for body text. User OS font scaling supported up to 200%.

---

## 4. Spacing Scale

Base unit: **4 dp**

| Token | Value | Usage |
|-------|-------|-------|
| `space-xs` | 4 | Icon padding |
| `space-sm` | 8 | Inline gaps |
| `space-md` | 16 | Card padding |
| `space-lg` | 24 | Section spacing |
| `space-xl` | 32 | Screen margins |
| `space-2xl` | 48 | Major section breaks |

---

## 5. Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius-sm` | 4 | Chips, badges |
| `radius-md` | 8 | Buttons, inputs |
| `radius-lg` | 12 | Cards |
| `radius-xl` | 16 | Bottom sheets, modals |
| `radius-full` | 999 | Avatars, pills |

---

## 6. Elevation & Shadows

| Level | Shadow | Usage |
|-------|--------|-------|
| 0 | none | Flat surfaces |
| 1 | `0 1px 3px rgba(26,26,46,0.08)` | Cards |
| 2 | `0 4px 12px rgba(26,26,46,0.12)` | FAB, dropdowns |
| 3 | `0 8px 24px rgba(26,26,46,0.16)` | Modals |

---

## 7. Core Components

### 7.1 Primary Button

- Background: `--color-primary`
- Text: white, `label-lg`
- Height: 48 dp minimum (touch target)
- Radius: `radius-md`
- Disabled: 40% opacity

### 7.2 Secondary Button

- Border: 1.5 px `--color-primary`
- Text: `--color-primary`
- Background: transparent

### 7.3 Restaurant Card

```
┌─────────────────────────────────────┐
│  [Icon]  Restaurant Name      4.5★ │
│          3.2 km · 25 min prep       │
│          NH-44, Murthal             │
└─────────────────────────────────────┘
```

- Padding: `space-md`
- Radius: `radius-lg`
- Elevation: level 1

### 7.4 Status Badge

- Pill shape (`radius-full`)
- Background: status color at 15% opacity
- Text: status color at 100%
- Font: `label-sm`

### 7.5 Countdown Timer

- Font: `mono`
- Color: `--color-warning` when < 15 min; `--color-error` when < 5 min
- Format: `45 min` or `04:32` for final 5 minutes

### 7.6 Map Pin

- Default restaurant: `--color-primary` pin
- Selected: `--color-accent` pin with pulse animation
- User location: blue dot (platform standard)

---

## 8. Iconography

**Library:** Material Symbols (Flutter `Icons` + custom SVGs)

| Concept | Icon |
|---------|------|
| Route | `route` |
| Restaurant | `restaurant` |
| Time / cutoff | `schedule` |
| Map | `map` |
| List | `list` |
| Order | `receipt_long` |
| Rating | `star` |

Icon size: 24 dp default; 20 dp inline; 32 dp empty states.

---

## 9. Map Styling (MapLibre)

- Base style: OpenStreetMap raster or liberty vector style
- Route polyline: `--color-accent`, 4 px width
- Corridor buffer: `--color-accent` at 10% fill opacity (Phase 2)
- Restaurant cluster: `--color-primary` circles with count label

**Attribution:** OSM attribution widget always visible (license requirement).

---

## 10. Dark Mode

Supported in Phase 2. Token overrides prepared:

| Light token | Dark equivalent |
|-------------|-----------------|
| `--color-surface` `#FFFCF7` | `#121218` |
| `--color-surface-elevated` `#FFFFFF` | `#1E1E28` |
| `--color-text-primary` `#1A1A2E` | `#F0EDE8` |
| `--color-border` `#E8E4DF` | `#2A2A36` |

MVP ships light mode only; tokens structured for future toggle.

---

## 11. Motion

| Animation | Duration | Easing |
|-----------|----------|--------|
| Button press | 100 ms | ease-out |
| Screen transition | 250 ms | ease-in-out |
| Status change | 300 ms | ease-out (fade + slide) |
| Map pin select | 200 ms | spring |

Respect `prefers-reduced-motion`: disable non-essential animations.

---

## 12. Flutter Theme Implementation

Central theme in `mobile/lib/theme/app_theme.dart`:

```dart
// Reference implementation shape — see 08_DEVELOPMENT_GUIDELINES.md
ThemeData(
  colorScheme: ColorScheme.light(
    primary: Color(0xFFE85D04),
    secondary: Color(0xFF1B4965),
    surface: Color(0xFFFFFCF7),
    error: Color(0xFFD62828),
  ),
  textTheme: GoogleFonts.interTextTheme(),
  elevatedButtonTheme: /* primary button spec */,
)
```

---

## 13. Related Documents

- [07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md) — Screen flows and UX patterns
- [08_DEVELOPMENT_GUIDELINES.md](./08_DEVELOPMENT_GUIDELINES.md) — Implementation conventions
