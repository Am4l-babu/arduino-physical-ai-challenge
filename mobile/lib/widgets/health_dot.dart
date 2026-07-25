import 'package:flutter/material.dart';
import '../theme/tokens.dart';

class HealthDot extends StatelessWidget {
  final DomoraState state;
  const HealthDot(this.state, {super.key});

  @override
  Widget build(BuildContext context) {
    final color = DomoraColors.forState(state);
    return Container(
      width: 9,
      height: 9,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        boxShadow: [BoxShadow(color: color.withValues(alpha: 0.35), blurRadius: 8)],
      ),
    );
  }
}

class DomoraChip extends StatelessWidget {
  final String text;
  final DomoraState? state;
  const DomoraChip(this.text, {super.key, this.state});

  @override
  Widget build(BuildContext context) {
    final color = state != null ? DomoraColors.forState(state!) : DomoraColors.inkDim;
    final bg = state != null ? color.withValues(alpha: 0.16) : DomoraColors.line;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s2, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(DomoraRadius.pill)),
      child: Text(
        text,
        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color, letterSpacing: 0.3),
      ),
    );
  }
}
