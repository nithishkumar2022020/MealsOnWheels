import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mealsonwheels/core/theme/motion.dart';

/// Builds [child] under a MediaQuery with the given reduced-motion setting.
Widget _wrap({required bool disableAnimations, required Widget child}) => MediaQuery(
  data: MediaQueryData(disableAnimations: disableAnimations),
  child: MaterialApp(home: child),
);

void main() {
  group('MowMotion.respecting', () {
    testWidgets('passes the duration through by default', (tester) async {
      late Duration resolved;

      await tester.pumpWidget(
        _wrap(
          disableAnimations: false,
          child: Builder(
            builder: (context) {
              resolved = MowMotion.respecting(context, MowMotion.screen);
              return const SizedBox();
            },
          ),
        ),
      );

      expect(resolved, MowMotion.screen);
      // The design system fixes this at 250 ms; a drift here is a spec change,
      // not a tweak.
      expect(MowMotion.screen, const Duration(milliseconds: 250));
    });

    testWidgets('collapses to zero when the OS asks for reduced motion', (
      tester,
    ) async {
      late Duration resolved;

      await tester.pumpWidget(
        _wrap(
          disableAnimations: true,
          child: Builder(
            builder: (context) {
              resolved = MowMotion.respecting(context, MowMotion.screen);
              return const SizedBox();
            },
          ),
        ),
      );

      // Zero, not merely shorter. Travellers enable this for vestibular
      // reasons, and this app runs on a moving bus.
      expect(resolved, Duration.zero);
    });
  });

  group('SlideFadeSwitcher', () {
    testWidgets('animates between children rather than cutting', (tester) async {
      final key = GlobalKey<_HostState>();

      await tester.pumpWidget(
        _wrap(disableAnimations: false, child: _Host(key: key)),
      );
      expect(find.text('first'), findsOneWidget);

      key.currentState!.swap();
      await tester.pump();
      // Mid-transition both are mounted — that overlap is the animation.
      await tester.pump(const Duration(milliseconds: 120));
      expect(find.text('second'), findsOneWidget);

      await tester.pumpAndSettle();
      expect(find.text('first'), findsNothing);
      expect(find.text('second'), findsOneWidget);
    });

    testWidgets('settles immediately under reduced motion', (tester) async {
      final key = GlobalKey<_HostState>();

      await tester.pumpWidget(
        _wrap(disableAnimations: true, child: _Host(key: key)),
      );

      key.currentState!.swap();
      // One frame, no duration pumped: with zero-length animations the new
      // child must already be the only one present.
      await tester.pump();
      await tester.pump();

      expect(find.text('first'), findsNothing);
      expect(find.text('second'), findsOneWidget);
    });
  });

  group('FadeSlideIn', () {
    testWidgets('reaches full opacity after the status duration', (tester) async {
      await tester.pumpWidget(
        _wrap(
          disableAnimations: false,
          child: const FadeSlideIn(child: Text('arrived')),
        ),
      );

      await tester.pumpAndSettle();

      final opacity = tester.widget<FadeTransition>(
        find.byType(FadeTransition).first,
      );
      expect(opacity.opacity.value, 1.0);
      expect(find.text('arrived'), findsOneWidget);
    });

    testWidgets('a delayed child still arrives', (tester) async {
      await tester.pumpWidget(
        _wrap(
          disableAnimations: false,
          child: const FadeSlideIn(
            delay: Duration(milliseconds: 60),
            child: Text('staggered'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      final opacity = tester.widget<FadeTransition>(
        find.byType(FadeTransition).first,
      );
      expect(opacity.opacity.value, 1.0);
    });

    testWidgets('disposing during the delay does not throw', (tester) async {
      // A booking that resolves while the user navigates away would otherwise
      // call forward() on a disposed controller.
      await tester.pumpWidget(
        _wrap(
          disableAnimations: false,
          child: const FadeSlideIn(
            delay: Duration(milliseconds: 200),
            child: Text('transient'),
          ),
        ),
      );

      await tester.pumpWidget(
        _wrap(disableAnimations: false, child: const SizedBox()),
      );
      await tester.pump(const Duration(milliseconds: 300));

      expect(tester.takeException(), isNull);
    });
  });
}

class _Host extends StatefulWidget {
  const _Host({super.key});

  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> {
  bool _second = false;

  void swap() => setState(() => _second = true);

  @override
  Widget build(BuildContext context) => SlideFadeSwitcher(
    child: _second
        ? const Text('second', key: ValueKey('second'))
        : const Text('first', key: ValueKey('first')),
  );
}
