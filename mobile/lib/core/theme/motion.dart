/// Motion tokens and shared transitions.
///
/// Durations and curves come from `docs/06_DESIGN_SYSTEM.md` §11, which the
/// crimson token document leaves in place. They live here rather than being
/// typed at each call site so a change is one edit, and so nobody invents a
/// 400 ms fade because it felt right in isolation.
///
/// **Every animation in this file collapses to zero when the OS asks.**
/// `MediaQuery.disableAnimationsOf` reflects "Reduce Motion" on iOS and
/// "Remove animations" on Android. Travellers who enable it often do so for
/// vestibular reasons — motion sickness on a moving bus is exactly the case
/// this app runs in — so it is honoured rather than merely shortened.
library;

import 'package:flutter/material.dart';

abstract final class MowMotion {
  /// Screen transition. 250 ms ease-in-out.
  static const screen = Duration(milliseconds: 250);

  /// Status change — fade + slide.
  static const status = Duration(milliseconds: 300);

  /// Map pin select, and other springy affordances.
  static const pin = Duration(milliseconds: 200);

  /// Button press feedback.
  static const press = Duration(milliseconds: 100);

  static const screenCurve = Curves.easeInOut;
  static const enterCurve = Curves.easeOutCubic;
  static const exitCurve = Curves.easeOut;

  /// Zero when the OS asks for reduced motion, otherwise [duration].
  ///
  /// Returning zero rather than skipping the widget keeps one code path: the
  /// animation still "runs", it simply completes instantly, so state changes
  /// and completion callbacks fire exactly as they would otherwise.
  static Duration respecting(BuildContext context, Duration duration) =>
      MediaQuery.disableAnimationsOf(context) ? Duration.zero : duration;
}

/// Forward/back transition for the auth flow and any linear sequence.
///
/// The outgoing screen fades and drifts slightly against the direction of
/// travel while the incoming one slides in — enough to say "you moved forward"
/// without the full-width push of a platform route, which would feel heavy on a
/// three-step flow the user re-enters often.
class SlideFadeSwitcher extends StatelessWidget {
  const SlideFadeSwitcher({
    super.key,
    required this.child,
    this.reverse = false,
  });

  final Widget child;

  /// True when navigating backwards, which mirrors the slide direction. Getting
  /// this wrong is subtle but reads as wrong: going "back" while the screen
  /// slides forward is disorienting in a way users notice without naming.
  final bool reverse;

  @override
  Widget build(BuildContext context) {
    final duration = MowMotion.respecting(context, MowMotion.screen);
    final begin = Offset(reverse ? -0.06 : 0.06, 0);

    return AnimatedSwitcher(
      duration: duration,
      switchInCurve: MowMotion.enterCurve,
      switchOutCurve: MowMotion.exitCurve,
      // The default lays the outgoing child over the incoming one, which
      // double-exposes text mid-fade. Stacking with the new child on top keeps
      // the arriving screen readable throughout.
      layoutBuilder: (current, previous) => Stack(
        alignment: Alignment.center,
        children: [...previous, ?current],
      ),
      transitionBuilder: (child, animation) => FadeTransition(
        opacity: animation,
        child: SlideTransition(
          position: Tween<Offset>(begin: begin, end: Offset.zero).animate(
            CurvedAnimation(parent: animation, curve: MowMotion.enterCurve),
          ),
          child: child,
        ),
      ),
      child: child,
    );
  }
}

/// Fade-and-rise for content appearing within a screen — a revealed form field,
/// an error banner, a result list.
///
/// [delay] staggers a group so items arrive in reading order rather than all at
/// once. Keep it small: a stagger long enough to notice is a stagger long
/// enough to wait for.
class FadeSlideIn extends StatefulWidget {
  const FadeSlideIn({
    super.key,
    required this.child,
    this.delay = Duration.zero,
    this.offset = 12,
  });

  final Widget child;
  final Duration delay;

  /// Vertical travel in logical pixels. Small on purpose — this is a hint of
  /// motion, not a slide.
  final double offset;

  @override
  State<FadeSlideIn> createState() => _FadeSlideInState();
}

class _FadeSlideInState extends State<FadeSlideIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: MowMotion.status,
  );

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    if (widget.delay > Duration.zero) {
      await Future<void>.delayed(widget.delay);
      // The widget can be disposed during the delay — a booking that resolves
      // while the user is navigating away, for instance.
      if (!mounted) return;
    }
    _controller.forward();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Read here rather than in initState: MediaQuery is not available yet at
    // initState, and reduced-motion can change while the app is running.
    _controller.duration = MowMotion.respecting(context, MowMotion.status);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final curved = CurvedAnimation(
      parent: _controller,
      curve: MowMotion.enterCurve,
    );

    return FadeTransition(
      opacity: curved,
      child: AnimatedBuilder(
        animation: curved,
        builder: (context, child) => Transform.translate(
          offset: Offset(0, widget.offset * (1 - curved.value)),
          child: child,
        ),
        child: widget.child,
      ),
    );
  }
}
