import 'dart:ui';
import 'package:flutter/material.dart';
import '../theme/tokens.dart';

/// The one glass surface every panel is built from — mirrors .glass in
/// studio/base.css (translucent + backdrop blur + hairline border).
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const GlassCard({super.key, required this.child, this.padding = const EdgeInsets.all(DomoraSpace.s4)});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(DomoraRadius.r2),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: DomoraColors.glassBg,
            borderRadius: BorderRadius.circular(DomoraRadius.r2),
            border: Border.all(color: DomoraColors.glassBorder),
          ),
          child: child,
        ),
      ),
    );
  }
}
