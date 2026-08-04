/// Welcome screen — `mockups/welcome_to_mealsonwheels`, re-skinned.
library;

import 'package:flutter/material.dart';

import '../../../core/theme/motion.dart';
import '../../../core/theme/tokens.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key, required this.onGetStarted});

  final VoidCallback onGetStarted;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(MowSpace.containerMargin),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(flex: 2),
              // Staggered in reading order — mark, then name, then promise.
              // 60 ms apart is enough to feel sequential without making anyone
              // wait for the button.
              const FadeSlideIn(child: _Mark()),
              const SizedBox(height: MowSpace.section),
              FadeSlideIn(
                delay: const Duration(milliseconds: 60),
                child: Text(
                  'Welcome to\nMealsOnWheels',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.displaySmall,
                ),
              ),
              const SizedBox(height: MowSpace.gutter),
              FadeSlideIn(
                delay: const Duration(milliseconds: 120),
                child: Text(
                  'Pre-book meals along your route. '
                  'Your food is ready the moment you arrive — no queue.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: MowColors.onSurfaceVariant,
                  ),
                ),
              ),
              const Spacer(flex: 3),
              FadeSlideIn(
                delay: const Duration(milliseconds: 180),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ElevatedButton(
                      onPressed: onGetStarted,
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('Get started'),
                          SizedBox(width: MowSpace.base),
                          Icon(Icons.arrow_forward, size: 20),
                        ],
                      ),
                    ),
                    const SizedBox(height: MowSpace.gutter),
                    // Single entry point: the login screen decides whether this
                    // is a sign-in or a sign-up once it knows the number. Two
                    // buttons here would make the user answer a question they
                    // cannot know.
                    Text(
                      'Sign in or create an account with your phone number',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: MowSpace.base),
            ],
          ),
        ),
      ),
    );
  }
}

class _Mark extends StatelessWidget {
  const _Mark();

  @override
  Widget build(BuildContext context) => Center(
    child: Container(
      height: 96,
      width: 96,
      decoration: BoxDecoration(
        color: MowColors.primary,
        borderRadius: BorderRadius.circular(MowRadius.xl),
      ),
      child: const Icon(
        Icons.local_shipping_outlined,
        color: MowColors.onPrimary,
        size: 48,
      ),
    ),
  );
}
