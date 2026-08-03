/// Typed failures, mapped from the backend's `{detail, code}` envelope.
///
/// **Branch on [code], never on [detail].** The detail strings are
/// human-readable and not stable copy; the codes are the contract
/// (docs/05_API_SPEC.md §2).
library;

import 'package:dio/dio.dart';

sealed class ApiFailure implements Exception {
  const ApiFailure(this.code, this.detail);

  final String code;
  final String detail;

  @override
  String toString() => '$runtimeType($code): $detail';
}

/// Not authenticated, or a token that cannot be trusted.
///
/// Deliberately indistinguishable from "valid token for a deleted user" and
/// "restaurant token on a traveller endpoint" — the server returns the same
/// 401 for all three so a caller probing tokens learns nothing.
class Unauthorized extends ApiFailure {
  const Unauthorized([String detail = 'Not authenticated'])
    : super('UNAUTHORIZED', detail);
}

/// Signature was valid but expired. Distinct from [Unauthorized] so the client
/// can say "log in again" rather than "something went wrong".
class TokenExpired extends ApiFailure {
  const TokenExpired([String detail = 'Session expired'])
    : super('TOKEN_EXPIRED', detail);
}

class InvalidOtp extends ApiFailure {
  const InvalidOtp([String detail = 'Incorrect code']) : super('INVALID_OTP', detail);
}

/// No account for this phone. **Not an error on the login path** — it is the
/// branch into registration. See docs/ui/05_SCREEN_API_WIRING.md §2.
class UserNotFound extends ApiFailure {
  const UserNotFound([String detail = 'No account for this number'])
    : super('USER_NOT_FOUND', detail);
}

class NotFound extends ApiFailure {
  const NotFound(super.code, super.detail);
}

class PhoneAlreadyRegistered extends ApiFailure {
  const PhoneAlreadyRegistered([String detail = 'This number is already registered'])
    : super('PHONE_ALREADY_REGISTERED', detail);
}

class Conflict extends ApiFailure {
  const Conflict(super.code, super.detail);
}

class ValidationFailure extends ApiFailure {
  const ValidationFailure(super.code, super.detail);
}

class RateLimited extends ApiFailure {
  const RateLimited(String detail, {this.retryAfter})
    : super('RATE_LIMITED', detail);

  final Duration? retryAfter;
}

/// The server is up but cannot do this right now — in practice, OTP delivery
/// with no SMS provider configured. Not retryable by the user.
class ServiceUnavailable extends ApiFailure {
  const ServiceUnavailable([String detail = 'Temporarily unavailable'])
    : super('SERVICE_UNAVAILABLE', detail);
}

class ServerError extends ApiFailure {
  const ServerError([String detail = 'Something went wrong'])
    : super('INTERNAL_ERROR', detail);
}

/// No response at all — airplane mode, no signal, server unreachable.
/// Separate from [ServerError] because the recovery is different: retry here,
/// report there.
class NetworkFailure extends ApiFailure {
  const NetworkFailure([String detail = 'No connection'])
    : super('NETWORK_ERROR', detail);
}

/// Converts a [DioException] into the typed failure for its code.
///
/// Every error the app handles passes through here, so the mapping lives in one
/// place rather than being re-derived per screen.
ApiFailure mapDioException(DioException e) {
  final response = e.response;

  if (response == null) {
    return switch (e.type) {
      DioExceptionType.connectionTimeout ||
      DioExceptionType.sendTimeout ||
      DioExceptionType.receiveTimeout => const NetworkFailure('The server took too long'),
      DioExceptionType.connectionError => const NetworkFailure(),
      _ => const NetworkFailure(),
    };
  }

  final body = response.data;
  // A proxy or gateway error returns HTML, not our envelope. Falling back to a
  // generic message beats showing the user a fragment of an error page.
  final code = body is Map && body['code'] is String ? body['code'] as String : null;
  final detail = body is Map && body['detail'] is String
      ? body['detail'] as String
      : 'Request failed (${response.statusCode})';

  return switch (code) {
    'TOKEN_EXPIRED' => TokenExpired(detail),
    'UNAUTHORIZED' => Unauthorized(detail),
    'INVALID_OTP' => InvalidOtp(detail),
    'USER_NOT_FOUND' => UserNotFound(detail),
    'PHONE_ALREADY_REGISTERED' => PhoneAlreadyRegistered(detail),
    'RATE_LIMITED' => RateLimited(detail, retryAfter: _retryAfter(response)),
    'SERVICE_UNAVAILABLE' => ServiceUnavailable(detail),
    'VALIDATION_ERROR' || 'UNPROCESSABLE_ENTITY' => ValidationFailure(code!, detail),
    _ => switch (response.statusCode) {
      401 => Unauthorized(detail),
      403 => Unauthorized(detail),
      404 => NotFound(code ?? 'NOT_FOUND', detail),
      409 => Conflict(code ?? 'CONFLICT', detail),
      422 => ValidationFailure(code ?? 'UNPROCESSABLE_ENTITY', detail),
      429 => RateLimited(detail, retryAfter: _retryAfter(response)),
      503 => ServiceUnavailable(detail),
      _ => ServerError(detail),
    },
  };
}

Duration? _retryAfter(Response<dynamic> response) {
  final raw = response.headers.value('retry-after');
  final seconds = raw == null ? null : int.tryParse(raw);
  return seconds == null ? null : Duration(seconds: seconds);
}
