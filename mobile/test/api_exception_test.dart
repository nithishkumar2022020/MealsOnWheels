import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mealsonwheels/core/api/api_exception.dart';

DioException _withBody(int status, Map<String, dynamic>? body, {Headers? headers}) {
  final options = RequestOptions(path: '/test');
  return DioException(
    requestOptions: options,
    type: DioExceptionType.badResponse,
    response: Response<Map<String, dynamic>>(
      requestOptions: options,
      statusCode: status,
      data: body,
      headers: headers,
    ),
  );
}

void main() {
  group('maps the backend error envelope by code', () {
    test('401 TOKEN_EXPIRED is distinct from UNAUTHORIZED', () {
      // The whole reason the backend emits two codes: expired means "log in
      // again", unauthorized means "this was never going to work".
      final expired = mapDioException(
        _withBody(401, {'code': 'TOKEN_EXPIRED', 'detail': 'Token has expired'}),
      );
      final unauthorized = mapDioException(
        _withBody(401, {'code': 'UNAUTHORIZED', 'detail': 'Invalid token'}),
      );

      expect(expired, isA<TokenExpired>());
      expect(unauthorized, isA<Unauthorized>());
    });

    test('404 USER_NOT_FOUND is its own type, not a generic NotFound', () {
      // It is the branch into registration, not an error state.
      final failure = mapDioException(
        _withBody(404, {'code': 'USER_NOT_FOUND', 'detail': 'No account'}),
      );
      expect(failure, isA<UserNotFound>());
    });

    test('404 NOT_FOUND stays generic', () {
      final failure = mapDioException(
        _withBody(404, {'code': 'NOT_FOUND', 'detail': 'Restaurant not found'}),
      );
      expect(failure, isA<NotFound>());
      expect(failure, isNot(isA<UserNotFound>()));
    });

    test('401 INVALID_OTP', () {
      expect(
        mapDioException(_withBody(401, {'code': 'INVALID_OTP', 'detail': 'Nope'})),
        isA<InvalidOtp>(),
      );
    });

    test('409 PHONE_ALREADY_REGISTERED', () {
      expect(
        mapDioException(
          _withBody(409, {'code': 'PHONE_ALREADY_REGISTERED', 'detail': 'Exists'}),
        ),
        isA<PhoneAlreadyRegistered>(),
      );
    });

    test('503 SERVICE_UNAVAILABLE', () {
      expect(
        mapDioException(
          _withBody(503, {'code': 'SERVICE_UNAVAILABLE', 'detail': 'No SMS'}),
        ),
        isA<ServiceUnavailable>(),
      );
    });

    test('422 validation', () {
      expect(
        mapDioException(
          _withBody(422, {'code': 'UNPROCESSABLE_ENTITY', 'detail': 'bad phone'}),
        ),
        isA<ValidationFailure>(),
      );
    });
  });

  group('429 rate limiting', () {
    test('reads Retry-After when present', () {
      final failure = mapDioException(
        _withBody(
          429,
          {'code': 'RATE_LIMITED', 'detail': 'Too many'},
          headers: Headers.fromMap({'retry-after': ['3600']}),
        ),
      );
      expect(failure, isA<RateLimited>());
      expect((failure as RateLimited).retryAfter, const Duration(seconds: 3600));
    });

    test('tolerates a missing Retry-After', () {
      final failure = mapDioException(
        _withBody(429, {'code': 'RATE_LIMITED', 'detail': 'Too many'}),
      );
      expect((failure as RateLimited).retryAfter, isNull);
    });
  });

  group('falls back safely', () {
    test('an HTML error page does not leak markup into the message', () {
      // A gateway 504 returns HTML, not our envelope. Showing the user a
      // fragment of an error page is worse than a generic message.
      final options = RequestOptions(path: '/test');
      final failure = mapDioException(
        DioException(
          requestOptions: options,
          type: DioExceptionType.badResponse,
          response: Response<String>(
            requestOptions: options,
            statusCode: 502,
            data: '<html>gateway timeout</html>',
          ),
        ),
      );
      expect(failure, isA<ServerError>());
      expect(failure.detail, isNot(contains('<html>')));
    });

    test('no response at all is a NetworkFailure, not a ServerError', () {
      // Different recovery: retry here, report there.
      final failure = mapDioException(
        DioException(
          requestOptions: RequestOptions(path: '/test'),
          type: DioExceptionType.connectionError,
        ),
      );
      expect(failure, isA<NetworkFailure>());
    });

    test('a timeout is a NetworkFailure', () {
      final failure = mapDioException(
        DioException(
          requestOptions: RequestOptions(path: '/test'),
          type: DioExceptionType.receiveTimeout,
        ),
      );
      expect(failure, isA<NetworkFailure>());
    });

    test('an unknown code falls through to the status code', () {
      final failure = mapDioException(
        _withBody(409, {'code': 'SOME_NEW_CODE', 'detail': 'Conflict'}),
      );
      expect(failure, isA<Conflict>());
      expect(failure.code, 'SOME_NEW_CODE');
    });
  });
}
