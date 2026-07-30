// AI Insights — observation cards derived from real twin/action state, not
// raw notifications forwarded as-is. Direct Dart port of studio/core/
// insights.js. Every card traces to a signal already shown elsewhere in the
// app (leak / dry-run / health / tank / NILM / action outcomes); this is a
// different, prioritized presentation of real state, not a new inference
// engine. See docs/APP_PLAN.md §4 Phase 5.
import 'nilm.dart';
import 'store.dart';

enum InsightPriority { critical, warning, info }

class Insight {
  final String id;
  final InsightPriority priority;
  final String text;
  final Map<String, dynamic> evidence;
  const Insight({required this.id, required this.priority, required this.text, this.evidence = const {}});
}

List<Insight> deriveInsights(DomoraStore store, List<NilmEntry> nilm) {
  final points = store.points;
  final cards = <Insight>[];

  dynamic get(String key, [dynamic dflt]) => points[key]?.value ?? dflt;

  if (get('virtual.water.leak_suspected', false) == true) {
    final ev = (get('virtual.water.leak_evidence') as Map?)?.cast<String, dynamic>() ?? const {};
    cards.add(Insight(
      id: 'leak',
      priority: InsightPriority.critical,
      text: 'Leak suspected on the main line: ${ev['flow_lpm'] ?? '?'} L/min flowing with the house empty, '
          'persistent for ${ev['persisted_ticks'] ?? '?'} ticks.',
      evidence: ev,
    ));
  }

  if (get('virtual.pump.dryrun_suspected', false) == true) {
    final ev = (get('virtual.pump.dryrun_evidence') as Map?)?.cast<String, dynamic>() ?? const {};
    cards.add(Insight(
      id: 'dryrun',
      priority: InsightPriority.critical,
      text: "Pump dry-run suspected: drawing ${ev['pump_current_a'] ?? '?'} A while the tank level isn't rising.",
      evidence: ev,
    ));
  }

  for (final entry in points.entries) {
    if (entry.key.startsWith('health.') && entry.value.value == 'suspect') {
      final asset = entry.key.substring('health.'.length);
      cards.add(Insight(
        id: 'health-$asset',
        priority: InsightPriority.warning,
        text: '${asset.replaceAll('_', ' ')} is flagged suspect by an independent sensor, '
            'not just a timed-out command.',
        evidence: {'asset': asset},
      ));
    }
  }

  final level = get('water_tank.level_pct');
  if (level is num && level < 15) {
    cards.add(Insight(
      id: 'tank-low',
      priority: InsightPriority.warning,
      text: 'Tank level is low: ${level.toStringAsFixed(0)}%.',
      evidence: {'level_pct': level},
    ));
  }

  for (final id in store.actionOrder) {
    final a = store.actions[id]!;
    if (a.status == 'failed') {
      cards.add(Insight(
        id: 'action-failed-${a.id}',
        priority: InsightPriority.critical,
        text: 'Action "${a.cause}" escalated: ${a.reason ?? 'verification failed'}.',
        evidence: {'action_id': a.id, 'command': a.command},
      ));
    } else if (a.status == 'pending' && a.retries > 0) {
      cards.add(Insight(
        id: 'action-retry-${a.id}',
        priority: InsightPriority.warning,
        text: 'Action "${a.cause}" has been retried ${a.retries}× and is still pending.',
        evidence: {'action_id': a.id},
      ));
    }
  }

  if (nilm.isNotEmpty) {
    final top = nilm.first;
    cards.add(Insight(
      id: 'nilm-top',
      priority: InsightPriority.info,
      text: '${top.name} used the most energy this session: ${top.energyWh.toStringAsFixed(2)} Wh.',
      evidence: {'appliance': top.name, 'energy_wh': top.energyWh},
    ));
  }

  if (cards.isEmpty) {
    cards.add(const Insight(
      id: 'nominal',
      priority: InsightPriority.info,
      text: 'Nothing to flag — the house reads nominal.',
    ));
  }

  cards.sort((a, b) => a.priority.index.compareTo(b.priority.index));
  return cards;
}
