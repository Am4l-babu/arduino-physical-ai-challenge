// Horizontal categorical bar chart — the NILM appliance breakdown. Port of
// studio/ui/bar-chart.js. Built from real widgets rather than one painted
// canvas so each row is independently tappable (drill-through to the
// appliance page) and reads correctly to screen readers; the mark spec —
// direct label per bar, so identity is never color-alone (see
// .claude/skills/dataviz) — is carried over unchanged.
import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class BarItem {
  final String label;
  final double value;
  const BarItem(this.label, this.value);
}

class DomoraBarChart extends StatelessWidget {
  final List<BarItem> items; // caller passes them pre-sorted, largest first
  final String unit;
  final String Function(double)? valueFmt;
  final void Function(BarItem)? onItemTap;

  const DomoraBarChart({
    super.key,
    required this.items,
    this.unit = '',
    this.valueFmt,
    this.onItemTap,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Text('No data yet.',
          style: TextStyle(color: DomoraColors.inkFaint, fontStyle: FontStyle.italic, fontSize: 13));
    }
    final fmt = valueFmt ?? ((v) => v.toStringAsFixed(2));
    final max = items.map((i) => i.value).fold<double>(0.001, (a, b) => a > b ? a : b);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < items.length; i++)
          _BarRow(
            item: items[i],
            fraction: (items[i].value / max).clamp(0.0, 1.0),
            color: DomoraColors.categorical[i % DomoraColors.categorical.length],
            valueLabel: '${fmt(items[i].value)}$unit',
            onTap: onItemTap == null ? null : () => onItemTap!(items[i]),
          ),
      ],
    );
  }
}

class _BarRow extends StatelessWidget {
  final BarItem item;
  final double fraction;
  final Color color;
  final String valueLabel;
  final VoidCallback? onTap;

  const _BarRow({
    required this.item,
    required this.fraction,
    required this.color,
    required this.valueLabel,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final row = Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(
              item.label,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 12, color: DomoraColors.inkDim),
            ),
          ),
          const SizedBox(width: DomoraSpace.s2),
          Expanded(
            child: Stack(
              children: [
                Container(
                  height: 18,
                  decoration: BoxDecoration(
                    color: DomoraColors.line,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                FractionallySizedBox(
                  widthFactor: fraction,
                  child: Container(
                    height: 18,
                    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: DomoraSpace.s2),
          SizedBox(
            width: 66,
            child: Text(
              valueLabel,
              style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: DomoraColors.ink),
            ),
          ),
          if (onTap != null)
            const Icon(Icons.chevron_right_rounded, size: 16, color: DomoraColors.inkFaint),
        ],
      ),
    );
    if (onTap == null) return row;
    return InkWell(onTap: onTap, borderRadius: BorderRadius.circular(DomoraRadius.r1), child: row);
  }
}
