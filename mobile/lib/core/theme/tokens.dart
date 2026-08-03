/// Design tokens — transcribed from docs/ui/03_DESIGN_TOKENS.md.
///
/// That document is the source of truth; this file is a transcription. If the
/// two disagree, the document is right. Never hardcode a colour or size in a
/// widget — add it here.
library;

import 'package:flutter/material.dart';

/// "Vibrant Transit" palette. Chosen by the owner over the teal alternative.
///
/// Every pair used for text has been contrast-checked against WCAG 2.1 AA —
/// see the ratios in the source document. Two results carry a warning:
///
/// - [outline] is 4.27:1 on [surface]: borders and disabled icons only, never
///   a label a traveller has to read. Use [onSurfaceVariant] (8.87) instead.
/// - [statusReadyFg] was darkened from the design system's `#2d936c`, which
///   scored 3.18 on its own tint and failed for text.
abstract final class MowColors {
  // Primary — "Hunger Red"
  static const primary = Color(0xFFB7122A);
  static const onPrimary = Color(0xFFFFFFFF);
  static const primaryContainer = Color(0xFFDB313F);
  static const onPrimaryContainer = Color(0xFFFFFBFF);
  static const inversePrimary = Color(0xFFFFB3B1);
  static const primaryFixed = Color(0xFFFFDAD8);
  static const onPrimaryFixed = Color(0xFF410007);

  // Secondary — "Road Grey"
  static const secondary = Color(0xFF5F5E5E);
  static const onSecondary = Color(0xFFFFFFFF);
  static const secondaryContainer = Color(0xFFE4E2E1);
  static const onSecondaryContainer = Color(0xFF656464);
  static const secondaryFixed = Color(0xFFE4E2E1);
  static const onSecondaryFixed = Color(0xFF1B1C1C);

  // Tertiary — amber, used for "cooking"/pending
  static const tertiary = Color(0xFF805200);
  static const onTertiary = Color(0xFFFFFFFF);
  static const tertiaryContainer = Color(0xFFA06900);
  static const tertiaryFixed = Color(0xFFFFDDB4);
  static const onTertiaryFixed = Color(0xFF291800);

  // Error
  static const error = Color(0xFFBA1A1A);
  static const onError = Color(0xFFFFFFFF);
  static const errorContainer = Color(0xFFFFDAD6);
  static const onErrorContainer = Color(0xFF93000A);

  // Surfaces
  static const surface = Color(0xFFF9F9F9);
  static const surfaceContainerLowest = Color(0xFFFFFFFF);
  static const surfaceContainerLow = Color(0xFFF3F3F3);
  static const surfaceContainer = Color(0xFFEEEEEE);
  static const surfaceContainerHigh = Color(0xFFE8E8E8);
  static const surfaceContainerHighest = Color(0xFFE2E2E2);
  static const surfaceDim = Color(0xFFDADADA);
  static const onSurface = Color(0xFF1A1C1C);
  static const onSurfaceVariant = Color(0xFF5B403F);
  static const inverseSurface = Color(0xFF2F3131);
  static const inverseOnSurface = Color(0xFFF1F1F1);
  static const outline = Color(0xFF8F6F6E);
  static const outlineVariant = Color(0xFFE4BEBC);
  static const surfaceTint = Color(0xFFBB162C);

  /// "Ready" status. Not in the Material set — see the class doc.
  static const statusReadyFg = Color(0xFF1E6B4D);
  static const statusReadyBg = Color(0xFFD7F0E5);
}

/// 8px base unit.
abstract final class MowSpace {
  static const xs = 4.0;
  static const base = 8.0;
  static const gutter = 16.0;
  static const containerMargin = 20.0;
  static const section = 32.0;

  /// Non-negotiable minimum tap target. Primary buttons are 56.
  static const touchTargetMin = 48.0;
  static const primaryButtonHeight = 56.0;
}

abstract final class MowRadius {
  static const sm = 4.0;
  static const base = 8.0;
  static const md = 12.0;

  /// Item cards, modal sheets.
  static const lg = 16.0;

  /// Bottom sheets.
  static const xl = 24.0;

  /// Pills. Reserved for badges and chips so they never read as buttons.
  static const full = 9999.0;
}

abstract final class MowElevation {
  /// Cards. A soft ambient lift, not a hard drop shadow.
  static const card = <BoxShadow>[
    BoxShadow(color: Color(0x0F000000), blurRadius: 20, offset: Offset(0, 4)),
  ];

  /// Floating actions — the "View Cart" bar.
  static const floating = <BoxShadow>[
    BoxShadow(color: Color(0x1A000000), blurRadius: 24, offset: Offset(0, 8)),
  ];
}
