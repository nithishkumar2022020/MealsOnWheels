/// Placeholder landing screen after sign-in.
///
/// Proves the token works by calling an authenticated endpoint. Replaced by the
/// home dashboard in Stage 4 — until then this is what confirms the round trip
/// end to end rather than just that login returned 200.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/tokens.dart';
import '../data/auth_repository.dart';
import '../domain/phone.dart';
import '../domain/user.dart';

final profileProvider = FutureProvider.autoDispose<User>(
  (ref) => ref.watch(authRepositoryProvider).profile(),
);

class SignedInScreen extends ConsumerWidget {
  const SignedInScreen({super.key, required this.onSignedOut});

  final VoidCallback onSignedOut;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final profile = ref.watch(profileProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('MealsOnWheels'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ref.read(authRepositoryProvider).signOut();
              onSignedOut();
            },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(MowSpace.containerMargin),
        child: profile.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Text(
              toApiFailure(error).detail,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
          ),
          data: (user) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("You're signed in", style: theme.textTheme.headlineMedium),
              const SizedBox(height: MowSpace.base),
              Text(
                'The token works — this came from an authenticated request '
                'to /user/profile.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: MowColors.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: MowSpace.section),
              _Row('Name', user.name ?? '—'),
              // Masked, matching the server's own logging rule. A full number
              // on screen is a small leak that costs nothing to avoid.
              _Row('Phone', maskPhone(user.phone)),
              _Row('Email', user.email ?? '—'),
              _Row('User ID', '#${user.id}'),
              const Spacer(),
              Text(
                'Route search lands in Stage 3.',
                style: theme.textTheme.labelSmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: MowSpace.gutter),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: theme.textTheme.labelSmall),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
