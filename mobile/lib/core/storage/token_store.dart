/// Token storage.
///
/// `flutter_secure_storage` (Keychain / Keystore), never `SharedPreferences`.
/// A JWT is valid for 24 hours and there is no server-side blocklist until
/// Phase 2, so a token read off a compromised device stays usable for a day
/// (docs/10_SECURITY.md §3.2).
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStore {
  const TokenStore(this._storage);

  final FlutterSecureStorage _storage;

  static const _travellerKey = 'traveller_token';
  static const _staffKey = 'staff_token';

  // Traveller and staff tokens are stored under separate keys rather than one
  // "current token". The backend distinguishes the two actors by a `typ` claim
  // and rejects a mismatch, so a single slot would let a staff login silently
  // break traveller requests and vice versa.
  Future<String?> readTraveller() => _storage.read(key: _travellerKey);
  Future<void> writeTraveller(String token) =>
      _storage.write(key: _travellerKey, value: token);
  Future<void> clearTraveller() => _storage.delete(key: _travellerKey);

  Future<String?> readStaff() => _storage.read(key: _staffKey);
  Future<void> writeStaff(String token) => _storage.write(key: _staffKey, value: token);
  Future<void> clearStaff() => _storage.delete(key: _staffKey);

  /// Signing out is client-side only: the token remains valid server-side for up
  /// to 24 hours. Documented, not an oversight — a blocklist is Phase 2.
  Future<void> clearAll() async {
    await clearTraveller();
    await clearStaff();
  }
}
