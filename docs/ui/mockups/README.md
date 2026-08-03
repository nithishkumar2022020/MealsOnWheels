# Stitch Mockups — 63 screens

**Source:** `stitch_mealsonwheels_transit_food_platform.zip`, generated in
[Stitch](https://stitch.withgoogle.com/) by the project owner, imported 2026-08-01.

Each directory holds one screen:

| File | What it is |
|------|-----------|
| `screen.png` | The rendered mockup, ~700×1600. **This is the visual source of truth.** |
| `code.html` | Stitch's Tailwind export. Useful for exact colours, spacing, and copy |

---

## How to use these

**Read `screen.png` first.** The HTML is machine-generated: it is faithful on colour and
copy, and unreliable on structure — deeply nested divs, duplicated bottom navs, absolute
positioning where a real layout would use flex. Treat it as a specimen, not a blueprint.

**Do not port the HTML to Flutter.** Widget structure comes from
[04_FLUTTER_ARCHITECTURE.md](../04_FLUTTER_ARCHITECTURE.md); colours and type come from
[03_DESIGN_TOKENS.md](../03_DESIGN_TOKENS.md), which resolves the inconsistencies below.
These files are what a screen should *look* like, not how to build it.

**Check [02_SCREEN_INVENTORY.md](../02_SCREEN_INVENTORY.md) before starting any screen.** It
records which of these 63 is canonical, which are variants of the same screen, and which
depend on backend work that does not exist yet.

---

## Known inconsistencies in the set

These are artefacts of generating 63 screens across several sessions, not deliberate design.
All are resolved in `03_DESIGN_TOKENS.md` — do not copy them into the app.

| Inconsistency | Detail | Resolution |
|---|---|---|
| **Two palettes** | 40 screens teal `#003441`; 23 crimson `#b7122a` | **Crimson wins** (owner decision, 2026-08-01) |
| **Two fonts** | 47 screens Montserrat only; 16 Inter + Montserrat | Montserrat display, Inter body |
| **Two currencies** | `$12.50` on some screens, `₹280` on others | **₹ INR only** — the product is Indian highways |
| **Three product names** | "MealsOnWheels", "TransitFood", "Sophisticated Transit" | **MealsOnWheels** |
| **Placeholder imagery** | Every `[img]` is a stock photo | The API returns **no images at all** — see inventory |

The teal screens are not wrong so much as earlier. Where a teal screen is the only version of
a layout, use its **structure** and re-skin it crimson.

---

## Deduplication, 2026-08-02

The import was 78 screens. **15 were deleted** — each was a teal recolour of a screen that
also existed in crimson, identical in layout and copy:

```
checkout_payment_2, checkout_payment_3, find_restaurants, home_dashboard_2,
live_order_tracking_2, live_order_tracking_3, onboarding_checklist,
operating_hours, order_update_required, restaurant_dashboard_enhanced,
restaurant_menu_2, restaurant_menu_3, route_search_screen_1,
route_search_screen_2, select_booking_type
```

**Same-name variants that survived are not duplicates.** `login_screen_1` / `_2`,
`booking_confirmed_modal_1` / `_2`, `restaurant_dashboard_admin_1` / `_2`,
`home_dashboard_1` / `_animated`, `live_order_tracking_1` / `_animated` / `_vibrant`,
`no_restaurants_found_empty_state_1` / `_2`, and `restaurant_list_map_view_1` / `_2` all
differ in layout or content — their PNGs were compared byte-wise and none matched. They are
genuine design iterations; deleting one would lose work.

`02_SCREEN_INVENTORY.md` §8 records which of each pair to prefer and why.

---

## Provenance and regeneration

These are vendored deliberately, at ~23 MB, because a design that lives only in someone's
Downloads folder stops being a source of truth the moment that laptop is unavailable — and
this repository's whole premise is that a new contributor can orient from the repo alone.

If the mockups are regenerated, replace this directory wholesale and update
`02_SCREEN_INVENTORY.md` in the same commit. A screen list that has drifted from the images
is worse than no list, because it is trusted.
