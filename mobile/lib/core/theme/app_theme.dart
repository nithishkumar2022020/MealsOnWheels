/// The single [ThemeData] for the app.
///
/// `ColorScheme.fromSeed` alone does not reproduce the palette — the explicit
/// `copyWith` is what makes it match `docs/ui/03_DESIGN_TOKENS.md`. Seeding
/// still matters: it fills the tonal roles this project has not named.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'tokens.dart';

abstract final class AppTheme {
  static ColorScheme get _lightScheme => ColorScheme.fromSeed(
    seedColor: MowColors.primary,
    brightness: Brightness.light,
  ).copyWith(
    primary: MowColors.primary,
    onPrimary: MowColors.onPrimary,
    primaryContainer: MowColors.primaryContainer,
    onPrimaryContainer: MowColors.onPrimaryContainer,
    inversePrimary: MowColors.inversePrimary,
    secondary: MowColors.secondary,
    onSecondary: MowColors.onSecondary,
    secondaryContainer: MowColors.secondaryContainer,
    onSecondaryContainer: MowColors.onSecondaryContainer,
    tertiary: MowColors.tertiary,
    onTertiary: MowColors.onTertiary,
    tertiaryContainer: MowColors.tertiaryContainer,
    error: MowColors.error,
    onError: MowColors.onError,
    errorContainer: MowColors.errorContainer,
    onErrorContainer: MowColors.onErrorContainer,
    surface: MowColors.surface,
    onSurface: MowColors.onSurface,
    onSurfaceVariant: MowColors.onSurfaceVariant,
    surfaceContainerLowest: MowColors.surfaceContainerLowest,
    surfaceContainerLow: MowColors.surfaceContainerLow,
    surfaceContainer: MowColors.surfaceContainer,
    surfaceContainerHigh: MowColors.surfaceContainerHigh,
    surfaceContainerHighest: MowColors.surfaceContainerHighest,
    surfaceDim: MowColors.surfaceDim,
    inverseSurface: MowColors.inverseSurface,
    onInverseSurface: MowColors.inverseOnSurface,
    outline: MowColors.outline,
    outlineVariant: MowColors.outlineVariant,
    surfaceTint: MowColors.surfaceTint,
  );

  /// Montserrat for headlines (geometric, urgent), Inter for everything
  /// functional (higher x-height, legible small on a moving bus).
  ///
  /// Sizes are deliberately larger than a typical app — the reader is in a
  /// vehicle. Nothing goes below 12.
  static TextTheme _textTheme(ColorScheme scheme) {
    final display = GoogleFonts.montserratTextTheme();
    final body = GoogleFonts.interTextTheme();

    return TextTheme(
      // headline-xl
      displaySmall: display.displaySmall!.copyWith(
        fontSize: 32,
        fontWeight: FontWeight.w700,
        height: 40 / 32,
        letterSpacing: -0.64, // −0.02em
        color: scheme.onSurface,
      ),
      // headline-lg
      headlineMedium: display.headlineMedium!.copyWith(
        fontSize: 24,
        fontWeight: FontWeight.w700,
        height: 32 / 24,
        color: scheme.onSurface,
      ),
      // headline-lg-mobile
      headlineSmall: display.headlineSmall!.copyWith(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        height: 28 / 20,
        color: scheme.onSurface,
      ),
      // body-lg
      bodyLarge: body.bodyLarge!.copyWith(
        fontSize: 18,
        fontWeight: FontWeight.w400,
        height: 28 / 18,
        color: scheme.onSurface,
      ),
      // body-md
      bodyMedium: body.bodyMedium!.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        height: 24 / 16,
        color: scheme.onSurface,
      ),
      // label-md
      labelLarge: body.labelLarge!.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        height: 20 / 14,
        letterSpacing: 0.14, // +0.01em
        color: scheme.onSurface,
      ),
      // label-sm — the floor. Never smaller.
      labelSmall: body.labelSmall!.copyWith(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        height: 16 / 12,
        color: scheme.onSurfaceVariant,
      ),
    );
  }

  static ThemeData get light {
    final scheme = _lightScheme;
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: _textTheme(scheme),
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.montserrat(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: scheme.onSurface,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: scheme.primary,
          foregroundColor: scheme.onPrimary,
          disabledBackgroundColor: scheme.primary.withValues(alpha: 0.4),
          disabledForegroundColor: scheme.onPrimary.withValues(alpha: 0.7),
          minimumSize: const Size.fromHeight(MowSpace.primaryButtonHeight),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(MowRadius.base),
          ),
          textStyle: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: scheme.primary,
          minimumSize: const Size.fromHeight(MowSpace.touchTargetMin),
          side: BorderSide(color: scheme.primary, width: 1.5),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(MowRadius.base),
          ),
          textStyle: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: scheme.primary,
          minimumSize: const Size(MowSpace.touchTargetMin, MowSpace.touchTargetMin),
          textStyle: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLowest,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: MowSpace.gutter,
          vertical: MowSpace.gutter,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MowRadius.base),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MowRadius.base),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MowRadius.base),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MowRadius.base),
          borderSide: BorderSide(color: scheme.error, width: 1.5),
        ),
        // Hints are decorative; labels carry the meaning. outline is not
        // AA-legible for text, so hints use it and nothing else does.
        hintStyle: GoogleFonts.inter(fontSize: 16, color: scheme.outline),
        labelStyle: GoogleFonts.inter(fontSize: 14, color: scheme.onSurfaceVariant),
      ),
      cardTheme: CardThemeData(
        color: scheme.surfaceContainerLowest,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MowRadius.lg),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: scheme.secondaryContainer,
        selectedColor: scheme.primaryFixed,
        labelStyle: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w500),
        shape: const StadiumBorder(),
        side: BorderSide.none,
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: scheme.inverseSurface,
        contentTextStyle: GoogleFonts.inter(
          fontSize: 14,
          color: scheme.onInverseSurface,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MowRadius.base),
        ),
      ),
    );
  }
}

/// Tabular figures, for anything that ticks or is money.
///
/// Proportional digits reflow as a countdown changes — 1 is narrower than 8 —
/// which makes a timer visibly jitter and a price column fail to align.
const tabularFigures = <FontFeature>[FontFeature.tabularFigures()];
