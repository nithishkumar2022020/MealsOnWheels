/// Temporary landing screen for Stage 1.
///
/// Exists to prove three things at a glance: the crimson theme renders, the
/// type scale is right, and the app can reach the backend. Replaced by the
/// welcome screen in Stage 2.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/endpoints.dart';
import '../../core/theme/tokens.dart';

/// Live check against `GET /api/health`, so the preview shows whether the
/// backend is actually reachable rather than assuming it.
final healthProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final dio = ref.watch(apiClientProvider);
  final response = await dio.get<Map<String, dynamic>>(Endpoints.health);
  return response.data ?? const {};
});

class ScaffoldHomeScreen extends ConsumerWidget {
  const ScaffoldHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final health = ref.watch(healthProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('MealsOnWheels')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(MowSpace.containerMargin),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Stage 1 scaffold', style: theme.textTheme.displaySmall),
            const SizedBox(height: MowSpace.base),
            Text(
              'Theme, API client, and token storage are wired. '
              'Screens land in Stage 2.',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: MowSpace.section),

            _SectionLabel('Backend'),
            const SizedBox(height: MowSpace.base),
            health.when(
              loading: () => const _StatusCard(
                label: 'Checking…',
                detail: 'Contacting the API',
                tone: _Tone.neutral,
              ),
              error: (error, _) => _StatusCard(
                label: 'Unreachable',
                detail: toApiFailure(error).detail,
                tone: _Tone.error,
              ),
              data: (data) => _StatusCard(
                label: 'Connected',
                detail: 'db: ${data['database']} · cache: ${data['redis']}',
                tone: _Tone.success,
              ),
            ),
            const SizedBox(height: MowSpace.section),

            _SectionLabel('Palette'),
            const SizedBox(height: MowSpace.base),
            const _Swatches(),
            const SizedBox(height: MowSpace.section),

            _SectionLabel('Type scale'),
            const SizedBox(height: MowSpace.base),
            Text('Ready for a feast?', style: theme.textTheme.headlineMedium),
            const SizedBox(height: MowSpace.xs),
            Text('Montserrat headline', style: theme.textTheme.labelSmall),
            const SizedBox(height: MowSpace.gutter),
            Text(
              'Food ready when you arrive. Pre-book along your route and skip '
              'the queue at the dhaba.',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: MowSpace.xs),
            Text('Inter body', style: theme.textTheme.labelSmall),
            const SizedBox(height: MowSpace.section),

            _SectionLabel('Buttons'),
            const SizedBox(height: MowSpace.base),
            ElevatedButton(onPressed: () {}, child: const Text('Primary action')),
            const SizedBox(height: MowSpace.base),
            OutlinedButton(onPressed: () {}, child: const Text('Secondary action')),
            const SizedBox(height: MowSpace.base),
            ElevatedButton(onPressed: null, child: const Text('Disabled')),
            const SizedBox(height: MowSpace.section),

            _SectionLabel('Order status'),
            const SizedBox(height: MowSpace.base),
            const Wrap(
              spacing: MowSpace.base,
              runSpacing: MowSpace.base,
              children: [
                _StatusBadge('Pending', Icons.schedule, MowColors.tertiary,
                    MowColors.tertiaryFixed),
                _StatusBadge('Confirmed', Icons.check_circle, MowColors.primary,
                    MowColors.primaryFixed),
                _StatusBadge('Ready', Icons.room_service, MowColors.statusReadyFg,
                    MowColors.statusReadyBg),
                _StatusBadge('Picked up', Icons.flag, MowColors.secondary,
                    MowColors.secondaryFixed),
                _StatusBadge('Cancelled', Icons.cancel, MowColors.error,
                    MowColors.errorContainer),
              ],
            ),
            const SizedBox(height: MowSpace.section),
          ],
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Text(
    text.toUpperCase(),
    style: Theme.of(context).textTheme.labelSmall?.copyWith(letterSpacing: 1.2),
  );
}

enum _Tone { neutral, success, error }

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.label, required this.detail, required this.tone});

  final String label;
  final String detail;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final (fg, bg) = switch (tone) {
      _Tone.success => (MowColors.statusReadyFg, MowColors.statusReadyBg),
      _Tone.error => (MowColors.onErrorContainer, MowColors.errorContainer),
      _Tone.neutral => (MowColors.onSecondaryContainer, MowColors.secondaryContainer),
    };

    return Container(
      padding: const EdgeInsets.all(MowSpace.gutter),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(MowRadius.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(color: fg),
          ),
          const SizedBox(height: MowSpace.xs),
          Text(
            detail,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(color: fg),
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge(this.label, this.icon, this.fg, this.bg);

  final String label;
  final IconData icon;
  final Color fg;
  final Color bg;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(
      horizontal: MowSpace.gutter,
      vertical: MowSpace.base,
    ),
    decoration: BoxDecoration(
      color: bg,
      borderRadius: BorderRadius.circular(MowRadius.full),
    ),
    // Icon *and* label: status is never encoded in colour alone.
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: fg),
        const SizedBox(width: MowSpace.xs),
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: fg,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    ),
  );
}

class _Swatches extends StatelessWidget {
  const _Swatches();

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: MowSpace.base,
    runSpacing: MowSpace.base,
    children: const [
      _Swatch('primary', MowColors.primary, MowColors.onPrimary),
      _Swatch('container', MowColors.primaryContainer, MowColors.onPrimaryContainer),
      _Swatch('secondary', MowColors.secondary, MowColors.onSecondary),
      _Swatch('tertiary', MowColors.tertiary, MowColors.onTertiary),
      _Swatch('error', MowColors.error, MowColors.onError),
    ],
  );
}

class _Swatch extends StatelessWidget {
  const _Swatch(this.label, this.color, this.onColor);

  final String label;
  final Color color;
  final Color onColor;

  @override
  Widget build(BuildContext context) => Container(
    width: 96,
    height: 64,
    padding: const EdgeInsets.all(MowSpace.base),
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(MowRadius.base),
    ),
    alignment: Alignment.bottomLeft,
    child: Text(
      label,
      style: Theme.of(context).textTheme.labelSmall?.copyWith(color: onColor),
    ),
  );
}
