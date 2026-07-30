// Phase C — Security. Port of studio/screens/security.js. Real data only:
// occupancy fusion (radar + PIR → house.occupied) and the real alert feed.
// Door/window/glass-break/smoke/gas have no simulator or hardware feeding
// the twin yet — no scenario in sim/ publishes them — so this screen says so
// plainly instead of fabricating widgets. See docs/APP_PLAN.md §7.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/store.dart';
import '../core/twin.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';
import '../widgets/incident_row.dart';

const _notConnected = [
  'Doors / windows',
  'Motion (beyond living-room radar+PIR)',
  'Glass break',
  'Smoke',
  'Gas',
];

class SecurityScreen extends StatelessWidget {
  const SecurityScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return AnimatedBuilder(animation: store, builder: (context, _) => _body(store));
  }

  Widget _body(DomoraStore store) {
    final occ = deriveOccupancy(store.points);
    final alerts = store.feed.where((f) => f.topic.startsWith('domora/alert')).toList();

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Occupancy'),
              Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: DomoraSpace.s2,
                runSpacing: 4,
                children: [
                  DomoraChip(occ.occupied ? 'occupied' : 'empty',
                      state: occ.occupied ? DomoraState.ok : DomoraState.learn),
                  Text('radar ${occ.radar ? "on" : "off"} · PIR ${occ.pir ? "on" : "off"}',
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkFaint)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Alerts'),
              if (alerts.isEmpty)
                const EmptyNote('No alerts in this run.')
              else
                for (final a in alerts) _AlertRow(entry: a),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Not yet connected'),
              for (final label in _notConnected) _NotConnectedRow(label: label),
            ],
          ),
        ),
      ],
    );
  }
}

class _AlertRow extends StatelessWidget {
  final FeedEntry entry;
  const _AlertRow({required this.entry});

  @override
  Widget build(BuildContext context) {
    final reason = entry.payload['reason'] as String?;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DomoraSpace.s1),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: DomoraSpace.s2,
            children: [
              const HealthDot(DomoraState.crit),
              Text(fmtTick(entry.t),
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkFaint)),
              Text(entry.topic,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.ink)),
            ],
          ),
          if (reason != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(reason, style: const TextStyle(fontSize: 12, color: DomoraColors.stCrit)),
            ),
        ],
      ),
    );
  }
}

/// A sensor class this system genuinely has no data source for. Saying so is
/// the point — an empty dot and "no node reporting this yet", never a fake
/// reading. See docs/APP_PLAN.md §7.
class _NotConnectedRow extends StatelessWidget {
  final String label;
  const _NotConnectedRow({required this.label});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: DomoraColors.inkFaint),
              ),
            ),
            const SizedBox(width: DomoraSpace.s2),
            Expanded(child: Text(label, style: const TextStyle(fontSize: 13, color: DomoraColors.inkDim))),
            const Text('no node reporting this yet',
                style: TextStyle(fontSize: 11, color: DomoraColors.inkFaint, fontStyle: FontStyle.italic)),
          ],
        ),
      );
}
