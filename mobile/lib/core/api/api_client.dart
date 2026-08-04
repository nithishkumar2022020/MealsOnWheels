/// The configured dio instance.
///
/// Three jobs and nothing else: attach the token, normalise errors, and keep
/// timeouts short enough that a traveller on a patchy highway connection gets an
/// answer rather than a spinner.
library;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../storage/token_store.dart';
import 'api_exception.dart';

/// Overridden at build time:
/// `--dart-define=API_BASE_URL=http://10.0.2.2:8000/api`
///
/// The default is the iOS simulator's view of the host. Android emulators need
/// `10.0.2.2` — `localhost` there is the emulator itself.
const _defaultBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000/api',
);

final secureStorageProvider = Provider<FlutterSecureStorage>(
  (ref) => const FlutterSecureStorage(
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  ),
);

final tokenStoreProvider = Provider<TokenStore>(
  (ref) => TokenStore(ref.watch(secureStorageProvider)),
);

/// Signalled when a request fails with an expired token, so the router can send
/// the user to login without every screen having to check.
class SessionExpired extends Notifier<bool> {
  @override
  bool build() => false;

  void trigger() => state = true;
  void acknowledge() => state = false;
}

final sessionExpiredProvider = NotifierProvider<SessionExpired, bool>(
  SessionExpired.new,
);

final apiClientProvider = Provider<Dio>((ref) {
  final tokens = ref.watch(tokenStoreProvider);

  final dio = Dio(
    BaseOptions(
      baseUrl: _defaultBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      contentType: Headers.jsonContentType,
      // Errors are mapped by the interceptor below, so dio must hand us the
      // response rather than throwing on any non-2xx.
      validateStatus: (status) => status != null && status < 500,
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await tokens.readTraveller();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onResponse: (response, handler) {
        final status = response.statusCode ?? 0;
        if (status >= 200 && status < 300) {
          return handler.next(response);
        }
        // A 4xx arrives here rather than as an error because of validateStatus.
        // Convert it so callers only ever see DioException for failures.
        handler.reject(
          DioException(
            requestOptions: response.requestOptions,
            response: response,
            type: DioExceptionType.badResponse,
          ),
          true,
        );
      },
      onError: (error, handler) async {
        final failure = mapDioException(error);

        if (failure is TokenExpired) {
          // Clear before signalling: a stale token on the next request would
          // produce a second expiry and a redirect loop.
          await tokens.clearTraveller();
          ref.read(sessionExpiredProvider.notifier).trigger();
        }

        if (kDebugMode) {
          debugPrint(
            '[api] ${error.requestOptions.method} '
            '${error.requestOptions.path} -> ${failure.code}',
          );
        }

        handler.reject(
          DioException(
            requestOptions: error.requestOptions,
            response: error.response,
            type: error.type,
            error: failure,
          ),
        );
      },
    ),
  );

  return dio;
});

/// Unwraps the typed failure a repository should rethrow.
///
/// Repositories call this so no screen ever sees a [DioException] — the UI layer
/// switches on [ApiFailure] subtypes, which are exhaustive.
ApiFailure toApiFailure(Object error) => switch (error) {
  final ApiFailure f => f,
  DioException(error: final ApiFailure f) => f,
  final DioException e => mapDioException(e),
  _ => const ServerError(),
};
