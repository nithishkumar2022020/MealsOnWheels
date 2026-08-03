import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/app_theme.dart';
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

  void _go(_Screen screen) => setState(() => _screen = screen);

  @override
  Widget build(BuildContext context) {
    return switch (_screen) {
      _Screen.welcome => WelcomeScreen(onGetStarted: () => _go(_Screen.login)),
      _Screen.login => LoginScreen(onSignedIn: () => _go(_Screen.signedIn)),
      _Screen.signedIn => SignedInScreen(onSignedOut: () => _go(_Screen.welcome)),
    };
  }
}
