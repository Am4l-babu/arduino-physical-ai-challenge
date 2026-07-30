// Phase D — Room detail. Port of studio/screens/room.js. One page per real
// zone from core/twin.dart's deriveZones() (living / utility / panel — the
// only zones this system actually has data for). Real points, real health,
// and the real action timeline where one genuinely applies to the zone. No 3D
// view, predictions, automation, or maintenance suggestions: none of that is
// computed anywhere in this codebase. See docs/APP_PLAN.md §7.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/store.dart';
import '../core/twin.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';
import '../widgets/incident_row.dart';
import '../widgets/line_chart.dart';
import 'sensor.dart';

class _ZoneDef {
  final String label;
  final List<String> pointKeys;
  final String? chartKey;
  final bool actionsRelevant;
  const _ZoneDef({required this.label, required this.pointKeys, this.chartKey, required this.actionsRelevant});
}

const zoneDefs = <String, _ZoneDef>{
  'living': _ZoneDef(
    label: 'Living',
    pointKeys: ['house.occupied', 'living.pir', 'living.radar'],
    actionsRelevant: false,
  ),
  'utility': _ZoneDef(
    label: 'Water / Utility',
    pointKeys: [
      'tank.line.flow_lpm', 'water_tank.level_pct', 'main_valve.valve_state',
      'pump.pump_state', 'pump.current_a', 'virtual.water.leak_suspected',
      'virtual.pump.dryrun_suspected', 'health.main_valve', 'health.pump',
    ],
    chartKey: 'water_tank.level_pct',
    actionsRelevant: true,
  ),
  'panel': _ZoneDef(
    label: 'Main Panel',
    pointKeys: ['main_panel.power_w'],
    chartKey: 'main_panel.power_w',
    actionsRelevant: false,
  ),
};

class RoomScreen extends StatelessWidget {
  final String id;
  const RoomScreen({super.key, required this.id});

  @override
  Widget build(BuildContext context) {
    final def = zoneDefs[id];
    final store = StoreScope.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(def?.label ?? 'Unknown room')),
      body: def == null
          ? ListView(
              padding: const EdgeInsets.all(DomoraSpace.s4),
              children: [
                GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const CardTitle('Unknown room'),
                      EmptyNote('No zone named "$id". Try Living, Water / Utility, or Main Panel from Home.'),
                    ],
                  ),
                ),
              ],
            )
          : AnimatedBuilder(animation: store, builder: (context, _) => _body(context, store, def)),
    );
  }

  Widget _body(BuildContext context, DomoraStore store, _ZoneDef def) {
    final zones = deriveZones(store.points);
    final zone = zones.firstWhere((z) => z.label == def.label,
        orElse: () => Zone(id: id, label: def.label, state: DomoraState.ok, detail: '—'));
    final water = deriveWater(store.points);
    final occ = deriveOccupancy(store.points);
    final powerW = derivePowerW(store.points);

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GlassCard(
          child: Row(
            children: [
              HealthDot(zone.state),
              const SizedBox(width: DomoraSpace.s3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(def.label,
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
                    Text(zone.detail,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkFaint)),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (def.chartKey != null) ...[
          const SizedBox(height: DomoraSpace.s4),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Trend — this session'),
                DomoraLineChart(
                  data: store.seriesFor(def.chartKey!),
                  valueFmt: (v) => v.toStringAsFixed(1),
                ),
              ],
            ),
          ),
        ],
        if (id == 'living') ...[
          const SizedBox(height: DomoraSpace.s4),
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
        ],
        if (id == 'utility') ...[
          const SizedBox(height: DomoraSpace.s3),
          Wrap(
            spacing: DomoraSpace.s2,
            runSpacing: DomoraSpace.s2,
            children: [
              DomoraChip(water.leak ? 'leak suspected' : 'no leak',
                  state: water.leak ? DomoraState.crit : DomoraState.ok),
              DomoraChip(water.dryrun ? 'pump dry-run' : 'pump nominal',
                  state: water.dryrun ? DomoraState.crit : DomoraState.ok),
            ],
          ),
        ],
        if (id == 'panel' && !powerW.isNaN) ...[
          const SizedBox(height: DomoraSpace.s4),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Power now'),
                Text(fmtWatts(powerW),
                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
              ],
            ),
          ),
        ],
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Points in this room'),
              for (final key in def.pointKeys)
                _PointRow(
                  pointKey: key,
                  value: store.points.containsKey(key) ? fmtValue(store.points[key]!.value) : '—',
                  onTap: () => pushScoped(context, SensorScreen(pointKey: key)),
                ),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CardTitle(def.actionsRelevant ? 'Autonomous actions in this room' : 'Autonomous actions'),
              if (!def.actionsRelevant)
                const EmptyNote(
                    'This system never acts on this room — only the water loop (utility) is autonomous today.')
              else if (store.actionOrder.isEmpty)
                const EmptyNote('No autonomous action yet in this run.')
              else
                for (final aid in store.actionOrder)
                  IncidentRow(action: store.actions[aid]!, detailed: false),
            ],
          ),
        ),
      ],
    );
  }
}

class _PointRow extends StatelessWidget {
  final String pointKey;
  final String value;
  final VoidCallback onTap;
  const _PointRow({required this.pointKey, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DomoraRadius.r1),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 7),
          child: Row(
            children: [
              Expanded(
                flex: 3,
                child: Text(pointKey,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkDim)),
              ),
              const SizedBox(width: DomoraSpace.s2),
              Expanded(
                flex: 2,
                child: Text(value,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.right,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.ink)),
              ),
              const Icon(Icons.chevron_right_rounded, size: 16, color: DomoraColors.inkFaint),
            ],
          ),
        ),
      );
}
