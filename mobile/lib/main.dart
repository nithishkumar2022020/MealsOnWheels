import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/app_theme.dart';
import 'features/scaffold_home/scaffold_home_screen.dart';

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
      home: const ScaffoldHomeScreen(),
    );
  }
}
