// Ported design tokens — single source of truth mirrors studio/tokens.css.
// Dark is the designed default (see docs/APP_PLAN.md §1); light values are
// carried for completeness but the app defaults to dark, same as Studio.
import 'package:flutter/material.dart';

class DomoraColors {
  DomoraColors._();

  // --- dark (default) ---
  static const bg0 = Color(0xFF06070A);
  static const bg1 = Color(0xFF0B0D12);
  static const bg2 = Color(0xFF12151C);
  static const ink = Color(0xFFEEF1F6);
  static const inkDim = Color(0xFFAAB2C0);
  static const inkFaint = Color(0xFF6B7484);
  static const line = Color(0x14FFFFFF); // rgba(255,255,255,.08)
  static const lineStrong = Color(0x24FFFFFF); // rgba(255,255,255,.14)

  static const glassBg = Color(0x8C161921); // rgba(22,25,33,.55)
  static const glassBorder = Color(0x1AFFFFFF);

  static const accent = Color(0xFF5EB1FF);
  static const accentInk = Color(0xFF04101F);

  // --- the five-color health vocabulary (docs/APP_PLAN.md §1) ---
  static const stOk = Color(0xFF3EE08A);
  static const stWarn = Color(0xFFF5B955);
  static const stCrit = Color(0xFFFF5D6C);
  static const stLearn = Color(0xFF6C8DFF);
  static const stPred = Color(0xFFC084FC);

  // --- categorical (validated via .claude/skills/dataviz — dark steps) ---
  static const cat1 = Color(0xFF3987E5); // blue
  static const cat2 = Color(0xFFD95926); // orange
  static const cat3 = Color(0xFF199E70); // aqua

  static const categorical = [cat1, cat2, cat3];

  static Color forState(DomoraState s) => switch (s) {
        DomoraState.ok => stOk,
        DomoraState.warn => stWarn,
        DomoraState.crit => stCrit,
        DomoraState.learn => stLearn,
        DomoraState.pred => stPred,
      };
}

enum DomoraState { ok, warn, crit, learn, pred }

class DomoraSpace {
  DomoraSpace._();
  static const s1 = 4.0, s2 = 8.0, s3 = 12.0, s4 = 16.0, s6 = 24.0, s8 = 32.0, s12 = 48.0;
}

class DomoraRadius {
  DomoraRadius._();
  static const r1 = 10.0, r2 = 16.0, r3 = 24.0, pill = 999.0;
}

ThemeData domoraDarkTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: DomoraColors.bg0,
    colorScheme: const ColorScheme.dark(
      primary: DomoraColors.accent,
      onPrimary: DomoraColors.accentInk,
      surface: DomoraColors.bg2,
      onSurface: DomoraColors.ink,
    ),
    textTheme: const TextTheme(
      bodyMedium: TextStyle(color: DomoraColors.ink, fontSize: 15),
      bodySmall: TextStyle(color: DomoraColors.inkFaint, fontSize: 12),
    ),
    fontFamily: 'Roboto',
    appBarTheme: const AppBarTheme(
      backgroundColor: DomoraColors.bg1,
      foregroundColor: DomoraColors.ink,
      elevation: 0,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: DomoraColors.bg1,
      selectedItemColor: DomoraColors.accent,
      unselectedItemColor: DomoraColors.inkFaint,
      type: BottomNavigationBarType.fixed,
    ),
    dividerColor: DomoraColors.line,
  );
}
