# Flutter Architecture & Conventions

**Status:** authoritative for `mobile/`. Read before writing any Dart.
**Parent:** [../08_DEVELOPMENT_GUIDELINES.md](../08_DEVELOPMENT_GUIDELINES.md)

---

## 1. Stack

Decided, not open. Each line has a reason; changing one is a decision to record in
[01_UI_BUILD_PLAN.md](./01_UI_BUILD_PLAN.md) §5.

| Concern | Choice | Why |
|---|---|---|
| State | **Riverpod** (`flutter_riverpod` + `riverpod_annotation`) | ADR: chosen from the start rather than migrating from `provider` later |
| HTTP | **dio** | Interceptors are the clean place for the auth header and 401 handling |
| Models | **freezed** + **json_serializable** | Unions make loading/error/data states exhaustive at compile time |
| Money | **decimal** | The API sends money as a string; `double` cannot hold ₹ safely |
| Token storage | **flutter_secure_storage** | Keychain/Keystore. `SharedPreferences` is plaintext — see `10_SECURITY.md` §3.2 |
| Routing | **go_router** | Declarative, deep-linkable, redirect hook for auth |
| Maps | **maplibre_gl** | Matches the backend's OSM/MapLibre commitment |
| Fonts | **google_fonts** | Montserrat + Inter |
| Time | **timezone** | Restaurant hours are per-restaurant local; UTC maths, local display |

```bash
flutter create --org com.mealsonwheels --platforms android,ios mobile
cd mobile
flutter pub add flutter_riverpod riverpod_annotation dio freezed_annotation \
  json_annotation decimal flutter_secure_storage go_router maplibre_gl \
  google_fonts timezone intl
flutter pub add -d build_runner freezed json_serializable riverpod_generator \
  custom_lint riverpod_lint
dart run build_runner watch -d      # keep running while developing
```

---

## 2. Structure

Feature-first. A feature owns its screens, widgets, controllers, and repository; `core/`
holds only what two or more features share.

```
mobile/lib/
├── main.dart
├── app.dart                       # MaterialApp.router + theme
├── core/
│   ├── theme/                     # app_theme.dart, tokens.dart  <- 03_DESIGN_TOKENS
│   ├── api/
│   │   ├── api_client.dart        # dio + interceptors
│   │   ├── api_exception.dart     # {detail, code} -> typed failure
│   │   └── endpoints.dart         # every path string, one place
│   ├── router/                    # app_router.dart, guards
│   ├── storage/                   # secure_storage.dart
│   ├── money.dart                 # Decimal <-> "80.00" + ₹ formatting
│   ├── time.dart                  # UTC parse, IST display, countdowns
│   └── widgets/                   # MowButton, StatusBadge, Countdown, ...
├── features/
│   ├── auth/         {data,domain,presentation}
│   ├── routes/
│   ├── restaurants/
│   ├── cart/
│   ├── bookings/
│   ├── ratings/
│   └── restaurant_admin/
└── l10n/
```

Inside a feature:

```
features/restaurants/
├── data/         restaurant_repository.dart, restaurant_api.dart
├── domain/       restaurant.dart, menu_item.dart          (freezed)
└── presentation/ restaurant_list_screen.dart, widgets/, controllers/
```

**A widget never calls dio.** Screen → controller (Riverpod) → repository → api client. A
`Text` that knows a URL is the thing this rule exists to prevent.

---

## 3. The API client

Three responsibilities, and nothing else: attach the token, normalise errors, parse money.

### 3.1 Errors

Every backend error is `{"detail": "...", "code": "..."}`. **Branch on `code`, never on
`detail`** — the messages are not stable copy.

```dart
sealed class ApiFailure implements Exception {
  const ApiFailure(this.code, this.detail);
  final String code;
  final String detail;
}

class Unauthorized      extends ApiFailure { /* UNAUTHORIZED */ }
class TokenExpired      extends ApiFailure { /* TOKEN_EXPIRED -> re-login */ }
class NotFound          extends ApiFailure { /* NOT_FOUND, USER_NOT_FOUND */ }
class Conflict          extends ApiFailure { /* PHONE_ALREADY_REGISTERED */ }
class RateLimited       extends ApiFailure { final Duration? retryAfter; }
class ServiceUnavailable extends ApiFailure { /* 503 — OTP unavailable */ }
class NetworkFailure    extends ApiFailure { /* no response at all */ }
```

An interceptor maps `DioException` → `ApiFailure` once, centrally. Handling
`TokenExpired` differently from `Unauthorized` is the whole reason the backend emits two
codes: expired means "log in again", unauthorized means "this was never going to work".

### 3.2 Money

```dart
// The API sends "80.00" — a string, deliberately.
Decimal parseMoney(String raw) => Decimal.parse(raw);
String formatInr(Decimal v) => '₹${v.toStringAsFixed(2)}';
```

`double.parse` here is a bug even though it compiles. Sum line items as `Decimal`.

**Never send a price to the server.** Booking requests carry name + qty only; a `price` field
is rejected with 422 by `extra="forbid"`. Display totals are a client-side preview — the
server's computed total is authoritative, so if they differ, show the server's and treat the
mismatch as a bug to report.

### 3.3 Unknown query parameters are silently ignored

Body fields are rejected (422); **query parameters are dropped without error**. A 200 from
`?sort=rating` does not mean sorting happened. Only send parameters listed in
[05_SCREEN_API_WIRING.md](./05_SCREEN_API_WIRING.md).

---

## 4. Time

- Everything from the API is **ISO 8601 UTC with `Z`**. Parse to UTC, convert only to display.
- **Do countdown maths in UTC.** `cutoff_time − now` in local time is right by accident and
  wrong across a DST or device-clock change.
- The device clock can be wrong. A countdown that has gone negative is a *cue to re-fetch*,
  not proof the cutoff passed — the server decides.
- Restaurant hours are in the restaurant's own timezone (`16` §3.1). Do not assume IST.

---

## 5. State conventions

```dart
@riverpod
class RestaurantSearch extends _$RestaurantSearch {
  @override
  Future<List<Restaurant>> build({required double lat, required double lon,
                                  double radiusKm = 15}) =>
      ref.read(restaurantRepositoryProvider).search(...);
}
```

- `AsyncValue` for anything loaded. Render all three of loading / error / data —
  `.when()` with a real error branch, never `data!`.
- Cart is `NotifierProvider`, in-memory only. It is cleared on successful booking and does
  **not** survive a kill: a stale cart priced against a changed menu is worse than an empty one.
- The auth token lives in secure storage; an `authStateProvider` exposes only
  signed-in/signed-out. Screens never read the token.

---

## 6. Theme

`core/theme/` mirrors [03_DESIGN_TOKENS.md](./03_DESIGN_TOKENS.md) exactly — that file is the
source, this is the transcription.

```dart
final lightScheme = ColorScheme.fromSeed(
  seedColor: const Color(0xFFB7122A),
  brightness: Brightness.light,
).copyWith(
  primary: const Color(0xFFB7122A),
  onPrimary: Colors.white,
  primaryContainer: const Color(0xFFDB313F),
  secondary: const Color(0xFF5F5E5E),
  error: const Color(0xFFBA1A1A),
  surface: const Color(0xFFF9F9F9),
  onSurface: const Color(0xFF1A1C1C),
  outline: const Color(0xFF8F6F6E),
);
```

`fromSeed` alone will not reproduce the palette — the explicit `copyWith` is what makes it
match. Do not hardcode a colour in a widget; if a token is missing, add it to `tokens.dart`.

Money and countdowns use `FontFeature.tabularFigures()` so a ticking timer does not reflow.

---

## 7. Accessibility

Not a polish pass. Retrofitting these means re-touching every widget.

- **48 dp minimum** tap targets; primary buttons 56 dp.
- `Semantics` labels on every icon-only button.
- Test at **200% font scale** — start with the booking status screen, the densest.
- The map always has a list equivalent. Pins are not an accessible-only affordance.
- Honour `MediaQuery.disableAnimations`.
- Never encode meaning in colour alone: status badges carry an icon **and** a label.
- `outline` (#8f6f6e) is 4.27:1 — borders and disabled icons only, never body text.

---

## 8. Testing

| Layer | Tool | What |
|---|---|---|
| Unit | `flutter_test` | Money parsing, countdowns, status transitions |
| Repository | `dio_adapter` / mocked client | Every `ApiFailure` branch |
| Widget | `flutter_test` | Empty, loading, error state per screen |
| Golden | `flutter_test` | Status badges, cards — catches token drift |

The one non-obvious test to write first: **an unrated restaurant renders "New", not 0★.**
Every seeded restaurant is unrated, so this is the common case, not an edge case.

---

## 9. Environment

```dart
// --dart-define=API_BASE_URL=http://10.0.2.2:8000/api
const apiBaseUrl = String.fromEnvironment('API_BASE_URL');
```

`10.0.2.2` is the Android emulator's route to the host; `localhost` is the emulator itself.
iOS simulator uses `localhost`. No secrets in the app — it holds a JWT it was given, nothing
more.

---

## 10. Related

- [01_UI_BUILD_PLAN.md](./01_UI_BUILD_PLAN.md) — what to build next
- [05_SCREEN_API_WIRING.md](./05_SCREEN_API_WIRING.md) — per-screen contracts
- [../FRONTEND_CONTRACT.md](../FRONTEND_CONTRACT.md) — verified response shapes
