import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'glass_card.dart';

class StatTile extends StatelessWidget {
  final String label;
  final String value;
  final DomoraState? state;
  final String? unit;
  const StatTile({super.key, required this.label, required this.value, this.state, this.unit});

  @override
  Widget build(BuildContext context) {
    final color = state != null ? DomoraColors.forState(state!) : DomoraColors.ink;
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s3, vertical: DomoraSpace.s3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: 0.5, color: DomoraColors.inkFaint)),
          const SizedBox(height: 4),
          // A long value ("1.86 kW" in a 3-up grid on a narrow phone) must
          // shrink to fit rather than overflow the tile — found by a widget
          // test on a real 420px surface, not by inspection.
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: color)),
                if (unit != null) ...[
                  const SizedBox(width: 4),
                  Text(unit!, style: const TextStyle(fontSize: 12, color: DomoraColors.inkFaint)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
