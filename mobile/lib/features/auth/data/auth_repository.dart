/// Auth repository.
///
/// Wraps the two endpoints and rethrows typed [ApiFailure]s, so no screen ever
/// sees a `DioException`.
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../../../core/storage/token_store.dart';
import '../domain/user.dart';

class AuthRepository {
  const AuthRepository(this._dio, this._tokens);

  final Dio _dio;
  final TokenStore _tokens;

  /// Creates an account. Throws [PhoneAlreadyRegistered] on 409.
  ///
  /// Does **not** return a token — registration and login are separate steps
  /// server-side, which is deliberate: login is the only thing that mints a
  /// token, so there is one code path to audit.
  Future<User> register({
    required String phone,
    String? name,
    String? email,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        Endpoints.authRegister,
        data: {
          'phone': phone,
          // Omit rather than send null: the schema forbids unknown fields but
          // accepts absent optional ones, and an explicit null reads as "clear
          // this" if the endpoint ever supports updates.
          if (name != null && name.trim().isNotEmpty) 'name': name.trim(),
          if (email != null && email.trim().isNotEmpty) 'email': email.trim(),
        },
      );
      return User.fromJson(response.data!);
    } catch (error) {
      throw toApiFailure(error);
    }
  }

  /// Verifies the OTP and stores the token.
  ///
  /// Throws [UserNotFound] when the phone has no account — on the login screen
  /// that is not an error but the branch into registration.
  Future<LoginResult> login({required String phone, required String otp}) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        Endpoints.authLogin,
        data: {'phone': phone, 'otp': otp},
      );
      final result = LoginResult.fromJson(response.data!);
      await _tokens.writeTraveller(result.accessToken);
      return result;
    } catch (error) {
      throw toApiFailure(error);
    }
  }

  Future<User> profile() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(Endpoints.userProfile);
      return User.fromJson(response.data!);
    } catch (error) {
      throw toApiFailure(error);
    }
  }

  /// Client-side only. The token stays valid server-side for up to 24 hours —
  /// there is no blocklist until Phase 2, and this is documented rather than
  /// papered over.
  Future<void> signOut() => _tokens.clearAll();
}

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(tokenStoreProvider),
  ),
);
