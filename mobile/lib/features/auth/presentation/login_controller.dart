/// Login flow state.
///
/// The interesting part is the register branch. The backend's login never
/// creates a user — an unknown phone is `404 USER_NOT_FOUND`, deliberately,
/// because auto-register plus a constant OTP would let anyone mint a token for
/// any number. The mockups have no register screen, so without this branch a
/// first-time traveller cannot get into the app at all
/// (docs/ui/05_SCREEN_API_WIRING.md §2).
///
/// Note the ordering that makes this safe: the server verifies the OTP *before*
/// looking the phone up, so a 404 only ever reaches us from a caller who has
/// already passed OTP verification. The register step is not reachable by
/// probing numbers.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/auth_repository.dart';
import '../domain/user.dart';

enum LoginStep {
  /// Phone + OTP.
  credentials,

  /// Reached only after a 404: the number is verified but has no account, so we
  /// collect a name and register.
  profile,
}

class LoginState {
  const LoginState({
    this.step = LoginStep.credentials,
    this.isSubmitting = false,
    this.failure,
    this.signedIn,
  });

  final LoginStep step;
  final bool isSubmitting;

  /// Set for inline field errors and banners. Cleared on every new submit.
  final ApiFailure? failure;

  /// Non-null once login succeeds.
  final UserSummary? signedIn;

  LoginState copyWith({
    LoginStep? step,
    bool? isSubmitting,
    ApiFailure? failure,
    bool clearFailure = false,
    UserSummary? signedIn,
  }) => LoginState(
    step: step ?? this.step,
    isSubmitting: isSubmitting ?? this.isSubmitting,
    failure: clearFailure ? null : (failure ?? this.failure),
    signedIn: signedIn ?? this.signedIn,
  );
}

class LoginController extends Notifier<LoginState> {
  @override
  LoginState build() => const LoginState();

  /// Attempts to sign in, registering first when on the profile step.
  ///
  /// Returns true on success. The caller navigates; this controller does not,
  /// so the flow stays testable without a widget tree.
  Future<bool> submit({
    required String phone,
    required String otp,
    String? name,
    String? email,
  }) async {
    if (state.isSubmitting) return false;
    state = state.copyWith(isSubmitting: true, clearFailure: true);

    final repository = ref.read(authRepositoryProvider);

    try {
      if (state.step == LoginStep.profile) {
        await repository.register(phone: phone, name: name, email: email);
      }

      final result = await repository.login(phone: phone, otp: otp);
      state = state.copyWith(isSubmitting: false, signedIn: result.user);
      return true;
    } on UserNotFound {
      // Not an error. The OTP was accepted; there is simply no account yet.
      state = state.copyWith(step: LoginStep.profile, isSubmitting: false);
      return false;
    } on PhoneAlreadyRegistered {
      // Lost a race: an account appeared between our 404 and this register.
      // Retrying the login is the right move, so drop back a step rather than
      // showing a dead end.
      state = state.copyWith(
        step: LoginStep.credentials,
        isSubmitting: false,
        failure: const PhoneAlreadyRegistered(
          'This number is already registered. Signing you in instead.',
        ),
      );
      return false;
    } on ApiFailure catch (failure) {
      state = state.copyWith(isSubmitting: false, failure: failure);
      return false;
    }
  }

  /// Returns to the phone/OTP step.
  ///
  /// Called when the user edits the phone number after being asked for a name:
  /// the 404 that sent them here was about the *old* number, so keeping them on
  /// the register step would create an account for a number they just changed.
  void resetToCredentials() {
    if (state.step == LoginStep.credentials) return;
    state = state.copyWith(step: LoginStep.credentials, clearFailure: true);
  }

  void clearFailure() {
    if (state.failure == null) return;
    state = state.copyWith(clearFailure: true);
  }
}

final loginControllerProvider = NotifierProvider<LoginController, LoginState>(
  LoginController.new,
);
