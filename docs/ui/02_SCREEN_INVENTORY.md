# Screen Inventory — 65 mockups, 57 distinct screens

**Source:** `mockups/` (63 screens + 2 theme specs).
**Deduplicated:** 2026-08-02 — 15 teal recolours of crimson screens were deleted.
Surviving same-name variants are genuinely different designs, not duplicates.

Read this before starting any screen. It tells you which file is canonical, what the screen
is for, which endpoint feeds it, and whether that endpoint exists.

---

## 1. How to read this

**Canonical** is the file to build from. Where a screen has variants, they are usually the
same layout in a different palette — build the canonical one and apply
[03_DESIGN_TOKENS.md](./03_DESIGN_TOKENS.md). Where a teal screen is the only version of a
layout, use its structure and re-skin it crimson.

`Backend` column:

| Mark | Meaning |
|------|---------|
| ✅ | Endpoint built and verified (Stages 7–10) |
| 🔨 | Specified, not built — Stages 11–13 |
| 📋 | Proposed in `16_FUNCTIONAL_PRODUCT_DATA.md`, needs sign-off |
| ❌ | **No backend design exists.** Needs product + schema work first |

---

## 2. Traveller — core booking flow

The path a traveller actually walks. Build in this order.

| # | Screen | Canonical | Variants | Backend | Notes |
|---|--------|-----------|----------|---------|-------|
| 1 | Welcome | `welcome_to_mealsonwheels` | — | — | Static. "Get started" / "Log in" |
| 2 | Login | `login_screen_1` | `_2` | ✅ `POST /auth/login` | **Needs a register path — see §7.1** |
| 3 | Onboarding carousel | `book_ahead_skip_queues`, `search_along_your_route`, `rate_your_experience` | — | — | 3 steps, skippable |
| 4 | Booking type | `select_booking_type_vibrant` | — | 📋 `booking_type` | 3 modes shown; a 4th is needed — §7.2 |
| 5 | Route search | `route_search_vibrant` | — | ✅ `GET /routes` | Origin/dest dropdowns + time |
| 6 | Home dashboard | `home_dashboard_1` | `_animated` | ✅ + 🔨 | Composite; degrade per-section |
| 7 | Restaurant list | `find_restaurants_vibrant` | — | ✅ `GET /restaurants/search` | Filters mostly unbacked — §7.3 |
| 8 | List + map | `restaurant_list_map_view_1` | `_2` | ✅ | MapLibre; no route line — §7.4 |
| 9 | Restaurant menu | `restaurant_menu_1` | — | ✅ `GET /restaurants/{id}` | `order_menu` is a 4th take |
| 10 | Cart / checkout | `checkout_payment_1` | — | 🔨 `POST /bookings/create` | **Payment UI is unbacked — §7.5** |
| 11 | Booking confirmed | `booking_confirmed_modal_1` | `_2` | 🔨 | Booking ID, copy-to-clipboard |
| 12 | Order status | `order_status_tracking_enhanced` | — | 🔨 `GET /bookings/{id}` | Poll 10 s; stop on terminal |
| 13 | Order ready | `order_ready_modal` | — | 🔨 | Push/poll transition to `ready` |
| 14 | Order receipt | `order_receipt` | — | 🔨 | Has payment + courier fields |
| 15 | Order history | `order_history` | — | 🔨 `GET /bookings` | Filter All/Completed/Cancelled |
| 16 | Rate order | `post_trip_rating_screen` | `rate_order_modal` | 🔨 `POST /ratings/create` | 3 dimensions, 1–5 each |
| 17 | Cancel order | `cancel_order_modal` | — | 🔨 `PUT /bookings/{id}/cancel` | Shows refund — §7.5 |

---

## 3. Traveller — supporting screens

| Screen | Canonical | Backend | Notes |
|--------|-----------|---------|-------|
| Profile & settings | `user_profile_settings` | ⚠️ partial | Read ✅; **edit, wallet, saved locations ❌** |
| Notifications | `notifications_center` | ❌ | No notification system exists at all |
| No notifications | `no_notifications` | ❌ | Empty state for the above |
| Help & FAQ | `help_faq` | — | Static content; no endpoint needed |

---

## 4. Traveller — empty, error, and edge states

The most valuable screens in the set. Wire these as you build each happy path, not after.

| Screen | Canonical | Trigger |
|--------|-----------|---------|
| No restaurants | `no_restaurants_found_empty_state_1` | Search returns `total_count: 0` |
| No restaurants (alt) | `no_restaurants_found_empty_state_2` | Same; pick one |
| No order history | `no_order_history` | `GET /bookings` empty |
| Network error | `network_error_state` | Any request fails / no connectivity |
| Connection error | `network_connection_error` | Search-specific failure |
| Offline mode | `offline_behavior_state` | Device offline; banner + disabled actions |
| Cutoff passed | `cutoff_time_passed_warning` | `400 ARRIVAL_TOO_SOON` |
| Booking expired | `expired_booking_state` | Cutoff passed on a pending booking |
| Restaurant busy | `restaurant_busy_warning` | ❌ No queue-depth field exists |
| Restaurant offline | `restaurant_offline_error` | 📋 `is_accepting_orders = false` |
| Item unavailable | `order_update_required_vibrant` | 📋 `ITEM_UNAVAILABLE` — the race in `16` §3.6 |
| Order timeout | `order_confirmation_timeout` | Create request slow/no response |
| Restaurant cancelled | `restaurant_cancellation_modal` | Restaurant cancels a confirmed order |
| GPS unavailable | `gps_unavailable_tracking` | ❌ Delivery only — §7.6 |

---

## 5. Restaurant owner

Reachable from the traveller login via "Already a restaurant? Sign in here".

| Screen | Canonical | Variants | Backend | Notes |
|--------|-----------|----------|---------|-------|
| Partner login | `restaurant_login` | — | 📋 `POST /restaurant/auth/login` | Phone + OTP. **Work in progress in the tree** |
| Onboarding checklist | `onboarding_checklist_vibrant` | — | 📋 | Profile / hours / menu / booking types |
| Kitchen dashboard | `restaurant_dashboard_admin_1` | `_2` | 🔨 `GET /dashboard/orders` | Confirm/reject + cutoff countdown |
| Kitchen dashboard (alt) | `restaurant_dashboard_vibrant` | — | 🔨 | Adds inline stock toggles |
| No orders | `no_orders_admin_dashboard` | `no_orders_yet_admin` | 🔨 | Empty feed |
| Menu management | `restaurant_menu_management` | `menu_management` | 📋 `GET/POST/PUT/DELETE /restaurant/menu` | Two takes; `restaurant_menu_management` is crimson |
| Edit menu item | `edit_menu_item_modal` | — | 📋 | Name, price, prep, category, image |
| Operating hours | `operating_hours_vibrant` | — | 📋 `PUT /restaurant/hours` | Per-weekday, `+1 day` for past-midnight |
| Restaurant settings | `restaurant_settings` | — | 📋 `PUT /restaurant/settings` | Status toggle, contact, prep band |
| Analytics | `restaurant_analytics_dashboard` | — | ❌ | Orders/revenue/rating/hourly — **no endpoint** |

**The shared `X-Restaurant-Token` cannot ship in production** — the server refuses it when
`ENVIRONMENT=production`. These screens depend on per-restaurant accounts
(`16` §3.3), which is why partner login is 📋 not 🔨.

---

## 6. Delivery partner — not in any backend plan

| Screen | Canonical | Backend |
|--------|-----------|---------|
| Partner welcome | `delivery_partner_welcome` | ❌ |
| Registration | `partner_registration` | ❌ |
| Document upload | `document_upload` | ❌ |
| How it works | `how_it_works_rider` | ❌ |
| Live tracking | `live_order_tracking_1` (+`_animated`, `_vibrant`) | ❌ |

Five screens plus the tracking family. See
[06_FULFILMENT_MODES.md](./06_FULFILMENT_MODES.md) for what delivery needs before any of
this can be wired.

---

## 7. Screens that need a decision before they can be built

Each of these is a mockup that cannot be wired as drawn. Listed so nobody discovers it
mid-implementation.

**7.1 Login has no register path.** The IA goes `Login → Search`, but the backend's login
never creates a user — an unknown phone is `404 USER_NOT_FOUND`, deliberately, because
auto-register plus a constant OTP lets anyone mint a token for any number. **A first-time
user cannot get in.** Add a "Create account" step or reveal a name field on 404.

**7.2 Booking type shows three modes, the product has four.** The mockups offer bus
boarding point, self-drive dine-in, self-drive takeaway. Rider-to-seat delivery — which the
tracking screens depict in detail — is not among them, and `16` §3.4 does not include it.

**7.3 Filters are mostly unbacked.** The list screen offers hygiene rating, fast prep, pure
veg, cuisine, and open-now. The API supports **none** of them: no sort parameter, no cuisine
field, no veg flag, no hours. Ratings are `null` for every seeded restaurant, so a
"Hygiene 4.0+" filter would return nothing.

**7.4 The map has no route line.** `routes.geometry` is NULL for all five routes — polylines
need OSRM, which is not set up. Search is point-radius and ignores `route_id`. Pins and a
user dot work; the corridor does not.

**7.5 Payment is entirely unbacked.** Checkout shows a wallet with a balance, UPI, cards, a
promo code, delivery fee, and taxes. The backend has **no payment system** and the charter
says pay at the counter. `bookings.payment_status` is `pending|paid` and nothing sets `paid`.
Cancellation shows a refund amount that cannot be computed.

**7.6 Live tracking assumes a fleet.** Rider name, photo, rating, vehicle number, live
position, "2 mins away", call/WhatsApp. None of it has a data source.

---

## 8. Reconciling duplicate copies

Where two screens do the same job, prefer:

- **`restaurant_menu_management`** over `menu_management` — crimson, and closer to the
  proposed endpoints.
- **`post_trip_rating_screen`** over `rate_order_modal` — full screen, matches the 3-dimension
  rating model.
- **`no_restaurants_found_empty_state_2`** over `_1` — its copy ("No restaurants are
  accepting orders for this route at this time") matches what search actually filters on.
- **`restaurant_dashboard_vibrant`** over `restaurant_dashboard_admin_1` for the order feed
  — the inline stock toggles match `16` §3.1's `is_available`.

---

## 9. Counts

| | Count |
|---|---|
| Files in `mockups/` | 65 (63 screens + 2 theme specs) |
| Distinct screens | **57** |
| Buildable today (✅) | ~12 |
| Blocked on Stages 11–13 (🔨) | ~15 |
| Blocked on `16` sign-off (📋) | ~9 |
| **No backend design at all (❌)** | **~14** |
| Static / no backend needed | ~7 |

---

## 10. Related

- [01_UI_BUILD_PLAN.md](./01_UI_BUILD_PLAN.md) — build order and progress
- [05_SCREEN_API_WIRING.md](./05_SCREEN_API_WIRING.md) — per-screen field mapping
- [06_FULFILMENT_MODES.md](./06_FULFILMENT_MODES.md) — the delivery question
- [../FRONTEND_CONTRACT.md](../FRONTEND_CONTRACT.md) — verified API shapes
