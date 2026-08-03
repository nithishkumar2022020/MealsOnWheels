import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/app_theme.dart';
import 'core/theme/motion.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/signed_in_screen.dart';
import 'features/auth/presentation/welcome_screen.dart';

void main() {
  runApp(const ProviderScope(child: MealsOnWheelsApp()));
}

class MealsOnWheelsApp extends StatelessWidget {
  const MealsOnWheelsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MealsOnWheels',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      // Light only for MVP. The tokens are structured for dark mode, but
      // shipping a half-checked dark palette is worse than not offering one.
      themeMode: ThemeMode.light,
      home: const AuthFlow(),
    );
  }
}

/// Navigation for the auth flow.
///
/// Deliberately a small state machine rather than go_router: there are three
/// screens and one linear path, and a router would add redirect rules for a
/// decision this makes in one line. go_router arrives in Stage 3, when there is
/// a tab bar and deep links to justify it.
enum _Screen { welcome, login, signedIn }

class AuthFlow extends StatefulWidget {
  const AuthFlow({super.key});

  @override
  State<AuthFlow> createState() => _AuthFlowState();
}

class _AuthFlowState extends State<AuthFlow> {
  _Screen _screen = _Screen.welcome;

  /// Whether the last move was backwards, so the transition can mirror itself.
  /// Compared by enum index because the flow is linear: welcome → login →
  /// signedIn. A branching flow would need an explicit direction argument.
  bool _reverse = false;

  void _go(_Screen next) => setState(() {
    _reverse = next.index < _screen.index;
    _screen = next;
  });

  @override
  Widget build(BuildContext context) {
    final screen = switch (_screen) {
      _Screen.welcome => WelcomeScreen(
        key: const ValueKey(_Screen.welcome),
        onGetStarted: () => _go(_Screen.login),
      ),
      _Screen.login => LoginScreen(
        key: const ValueKey(_Screen.login),
        onSignedIn: () => _go(_Screen.signedIn),
        onBack: () => _go(_Screen.welcome),
      ),
      _Screen.signedIn => SignedInScreen(
        key: const ValueKey(_Screen.signedIn),
        onSignedOut: () => _go(_Screen.welcome),
      ),
    };

    // The key is what tells AnimatedSwitcher these are different screens; two
    // screens of the same runtime type without distinct keys would cross-fade
    // into themselves and appear not to animate at all.
    return SlideFadeSwitcher(reverse: _reverse, child: screen);
  }
}
