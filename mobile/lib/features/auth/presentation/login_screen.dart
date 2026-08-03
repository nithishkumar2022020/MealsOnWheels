/// Login, with the registration branch that makes first-time sign-in possible.
///
/// Follows `mockups/login_screen_1` — logo, phone with a fixed +91 prefix, OTP,
/// primary action, restaurant link — re-skinned to the crimson tokens. Two
/// deliberate departures from the mockup:
///
/// 1. The mockup's six separate OTP boxes are one field. Six boxes need focus
///    juggling that breaks paste, breaks SMS autofill, and confuses screen
///    readers, for a purely decorative gain.
/// 2. A name step appears after a 404, because the mockup has no register
///    screen and login does not create accounts.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/motion.dart';
import '../../../core/theme/tokens.dart';
import '../domain/phone.dart';
import 'login_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.onSignedIn, this.onBack});

  final VoidCallback? onSignedIn;

  /// Back to welcome. Also wired to the system back gesture so Android's
  /// hardware back does not drop the user out of the app mid-sign-in.
  final VoidCallback? onBack;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phone = TextEditingController();
  final _otp = TextEditingController();
  final _name = TextEditingController();
  final _email = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Editing the phone invalidates the 404 that sent us to the name step.
    _phone.addListener(() {
      ref.read(loginControllerProvider.notifier).resetToCredentials();
    });
  }

  @override
  void dispose() {
    _phone.dispose();
    _otp.dispose();
    _name.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();

    final signedIn = await ref.read(loginControllerProvider.notifier).submit(
      phone: toE164(_phone.text),
      otp: _otp.text.trim(),
      name: _name.text,
      email: _email.text,
    );

    if (signedIn && mounted) widget.onSignedIn?.call();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(loginControllerProvider);
    final isRegistering = state.step == LoginStep.profile;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        // On the register step, back returns to the phone/OTP step rather than
        // leaving the screen — the user is one field from an account, and
        // dropping them to welcome would discard a verified OTP.
        if (isRegistering) {
          ref.read(loginControllerProvider.notifier).resetToCredentials();
        } else {
          widget.onBack?.call();
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(MowSpace.containerMargin),
              child: ConstrainedBox(
                // Keeps the form readable on a tablet or a wide simulator rather
                // than stretching inputs the full width.
                constraints: const BoxConstraints(maxWidth: 420),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const _Brand(),
                      const SizedBox(height: MowSpace.section),

                      // Errors arrive rather than appear — an inline jump is
                      // easy to miss when you are looking at the field you just
                      // corrected.
                      AnimatedSize(
                        duration: MowMotion.respecting(context, MowMotion.status),
                        curve: MowMotion.enterCurve,
                        alignment: Alignment.topCenter,
                        child: state.failure == null
                            ? const SizedBox(width: double.infinity)
                            : Padding(
                                padding: const EdgeInsets.only(
                                  bottom: MowSpace.gutter,
                                ),
                                child: FadeSlideIn(
                                  key: ValueKey(state.failure!.code),
                                  child: _FailureBanner(state.failure!),
                                ),
                              ),
                      ),

                      _Label('Phone number'),
                      const SizedBox(height: MowSpace.base),
                      TextFormField(
                        controller: _phone,
                        keyboardType: TextInputType.phone,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.telephoneNumber],
                        inputFormatters: [
                          LengthLimitingTextInputFormatter(18),
                        ],
                        decoration: const InputDecoration(
                          hintText: 'Enter 10-digit mobile number',
                          prefixIcon: _CountryCodePrefix(),
                          prefixIconConstraints: BoxConstraints(minWidth: 56),
                        ),
                        validator: validatePhoneInput,
                      ),
                      const SizedBox(height: MowSpace.gutter),

                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _Label('Verification code'),
                          Text(
                            'Use 123456',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: MowColors.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: MowSpace.base),
                      TextFormField(
                        controller: _otp,
                        keyboardType: TextInputType.number,
                        textInputAction:
                            isRegistering ? TextInputAction.next : TextInputAction.done,
                        autofillHints: const [AutofillHints.oneTimeCode],
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(8),
                        ],
                        style: const TextStyle(
                          fontFeatures: [FontFeature.tabularFigures()],
                          letterSpacing: 8,
                        ),
                        decoration: const InputDecoration(hintText: '––––––'),
                        validator: validateOtp,
                        onFieldSubmitted: (_) => isRegistering ? null : _submit(),
                      ),

                      // The register branch. Only ever shown after the server
                      // has told us this verified number has no account, so it
                      // animates in as a consequence of an action rather than
                      // appearing unprompted.
                      AnimatedSize(
                        duration: MowMotion.respecting(context, MowMotion.status),
                        curve: MowMotion.enterCurve,
                        alignment: Alignment.topCenter,
                        child: !isRegistering
                            ? const SizedBox(width: double.infinity)
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  const SizedBox(height: MowSpace.gutter),
                                  const FadeSlideIn(child: _NewAccountNotice()),
                                  const SizedBox(height: MowSpace.gutter),
                                  FadeSlideIn(
                                    delay: const Duration(milliseconds: 60),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.stretch,
                                      children: [
                                        _Label('Your name'),
                                        const SizedBox(height: MowSpace.base),
                                        TextFormField(
                                          controller: _name,
                                          textCapitalization:
                                              TextCapitalization.words,
                                          textInputAction: TextInputAction.next,
                                          autofillHints: const [
                                            AutofillHints.name,
                                          ],
                                          decoration: const InputDecoration(
                                            hintText: 'Priya Sharma',
                                          ),
                                          validator: (v) =>
                                              (v ?? '').trim().isEmpty
                                              ? 'Enter your name'
                                              : null,
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(height: MowSpace.gutter),
                                  FadeSlideIn(
                                    delay: const Duration(milliseconds: 120),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.stretch,
                                      children: [
                                        Row(
                                          children: [
                                            _Label('Email'),
                                            const SizedBox(width: MowSpace.base),
                                            Text(
                                              'optional',
                                              style: theme.textTheme.labelSmall
                                                  ?.copyWith(
                                                    color: MowColors
                                                        .onSurfaceVariant,
                                                  ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: MowSpace.base),
                                        TextFormField(
                                          controller: _email,
                                          keyboardType:
                                              TextInputType.emailAddress,
                                          textInputAction: TextInputAction.done,
                                          autofillHints: const [
                                            AutofillHints.email,
                                          ],
                                          decoration: const InputDecoration(
                                            hintText: 'priya@example.com',
                                          ),
                                          validator: (v) {
                                            final value = (v ?? '').trim();
                                            if (value.isEmpty) return null;
                                            // Deliberately loose. The server
                                            // does the real check; rejecting an
                                            // address the server would accept is
                                            // worse than letting one 422 through.
                                            return value.contains('@') &&
                                                    value.contains('.')
                                                ? null
                                                : 'Enter a valid email, or leave it blank';
                                          },
                                          onFieldSubmitted: (_) => _submit(),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                      ),

                      const SizedBox(height: MowSpace.section),
                      // Not wrapped in PressScale: an ElevatedButton already
                      // has its own press feedback, and a GestureDetector over
                      // it would compete for the tap.
                      ElevatedButton(
                        onPressed: state.isSubmitting ? null : _submit,
                        child: AnimatedSwitcher(
                          duration: MowMotion.respecting(
                            context,
                            MowMotion.status,
                          ),
                          child: state.isSubmitting
                              ? const SizedBox(
                                  key: ValueKey('busy'),
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: MowColors.onPrimary,
                                  ),
                                )
                              : Text(
                                  isRegistering ? 'Create account' : 'Continue',
                                  key: ValueKey(isRegistering),
                                ),
                        ),
                      ),

                      const SizedBox(height: MowSpace.section),
                      const _RestaurantLink(),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Brand extends StatelessWidget {
  const _Brand();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Container(
          height: 72,
          width: 72,
          decoration: BoxDecoration(
            color: MowColors.primary,
            borderRadius: BorderRadius.circular(MowRadius.lg),
          ),
          child: const Icon(
            Icons.local_shipping_outlined,
            color: MowColors.onPrimary,
            size: 36,
          ),
        ),
        const SizedBox(height: MowSpace.gutter),
        Text('MealsOnWheels', style: theme.textTheme.displaySmall),
        const SizedBox(height: MowSpace.base),
        Text(
          'Food ready when you arrive.',
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: MowColors.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _CountryCodePrefix extends StatelessWidget {
  const _CountryCodePrefix();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(left: MowSpace.gutter, right: MowSpace.base),
    child: Text(
      defaultCountryCode,
      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
        fontWeight: FontWeight.w600,
        color: MowColors.onSurface,
      ),
    ),
  );
}

class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: Theme.of(context).textTheme.labelLarge,
  );
}

/// Shown when a verified number turns out to have no account.
///
/// Phrased as a next step rather than an error: nothing has gone wrong, and
/// "not found" would read as a failure the user must fix.
class _NewAccountNotice extends StatelessWidget {
  const _NewAccountNotice();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(MowSpace.gutter),
      decoration: BoxDecoration(
        color: MowColors.primaryFixed,
        borderRadius: BorderRadius.circular(MowRadius.lg),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.person_add_alt, size: 20, color: MowColors.onPrimaryFixed),
          const SizedBox(width: MowSpace.base),
          Expanded(
            child: Text(
              "You're new here — tell us your name and we'll set up your account.",
              style: theme.textTheme.labelLarge?.copyWith(
                color: MowColors.onPrimaryFixed,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Maps a failure to copy a traveller can act on.
///
/// Switches on the failure type, never on the message — the server's `detail`
/// is not stable copy.
class _FailureBanner extends StatelessWidget {
  const _FailureBanner(this.failure);

  final ApiFailure failure;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final (message, tone) = switch (failure) {
      InvalidOtp() => ('That code is incorrect. Try again.', _Tone.error),
      RateLimited(:final retryAfter) => (
        retryAfter == null
            ? 'Too many attempts. Try again shortly.'
            : 'Too many attempts. Try again in ${retryAfter.inMinutes} minutes.',
        _Tone.warning,
      ),
      // Not retryable by the user — production has no SMS provider, so saying
      // "try again" would be a lie.
      ServiceUnavailable() => (
        'Phone verification is temporarily unavailable. Please try later.',
        _Tone.warning,
      ),
      NetworkFailure() => (
        "Can't reach the server. Check your connection and try again.",
        _Tone.warning,
      ),
      PhoneAlreadyRegistered(:final detail) => (detail, _Tone.warning),
      ValidationFailure() => ('Check the details and try again.', _Tone.error),
      _ => ('Something went wrong. Please try again.', _Tone.error),
    };

    final (fg, bg) = switch (tone) {
      _Tone.error => (MowColors.onErrorContainer, MowColors.errorContainer),
      _Tone.warning => (MowColors.onTertiaryFixed, MowColors.tertiaryFixed),
    };

    return Container(
      padding: const EdgeInsets.all(MowSpace.gutter),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(MowRadius.lg),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            tone == _Tone.error ? Icons.error_outline : Icons.info_outline,
            size: 20,
            color: fg,
          ),
          const SizedBox(width: MowSpace.base),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.labelLarge?.copyWith(
                color: fg,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

enum _Tone { error, warning }

class _RestaurantLink extends StatelessWidget {
  const _RestaurantLink();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Row(
          children: [
            const Expanded(child: Divider()),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: MowSpace.gutter),
              child: Text('OR', style: theme.textTheme.labelSmall),
            ),
            const Expanded(child: Divider()),
          ],
        ),
        const SizedBox(height: MowSpace.gutter),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Already a restaurant?',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: MowColors.onSurfaceVariant,
              ),
            ),
            TextButton(
              // Restaurant staff auth exists server-side but has no screen yet.
              // A dead link is worse than an honest "coming soon".
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Restaurant sign-in is coming soon')),
              ),
              child: const Text('Sign in here'),
            ),
          ],
        ),
      ],
    );
  }
}
