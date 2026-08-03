/// Every API path, in one place.
///
/// Only paths that exist. Stage 11–13 endpoints are listed but commented, so
/// nobody wires a screen to a route the server does not serve yet — a 404 from
/// a typo and a 404 from an unbuilt endpoint look identical at the call site.
library;

abstract final class Endpoints {
  // --- Built and verified (backend Stages 7–10) ---
  static const health = '/health';

  static const authRegister = '/auth/register';
  static const authLogin = '/auth/login';
  static const userProfile = '/user/profile';

  static const routes = '/routes';

  static const restaurantSearch = '/restaurants/search';
  static String restaurantDetail(int id) => '/restaurants/$id';
  static const restaurantRegister = '/restaurants/register';

  // --- Not built. Uncomment as each backend stage lands. ---
  // Stage 11 — bookings
  // static const bookingsCreate = '/bookings/create';
  // static const bookings = '/bookings';
  // static String booking(int id) => '/bookings/$id';
  // static String bookingCancel(int id) => '/bookings/$id/cancel';

  // Stage 13 — ratings
  // static const ratingsCreate = '/ratings/create';

  // Proposed in docs/16 — needs sign-off before use
  // static const restaurantAuthLogin = '/restaurant/auth/login';
  // static const restaurantMenu = '/restaurant/menu';
}
