// Phase A — Live Home: direct port of studio/screens/home.js. Every value
// shown is bound to a real twin point or cognition event.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/store.dart';
import '../core/twin.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';
import '../widgets/stat_tile.dart';
import 'room.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) => _HomeBody(store: store),
    );
  }
}

class _HomeBody extends StatelessWidget {
  final DomoraStore store;
  const _HomeBody({required this.store});

  @override
  Widget build(BuildContext context) {
    final points = store.points;
    final water = deriveWater(points);
    final occ = deriveOccupancy(points);
    final powerW = derivePowerW(points);
    final zones = deriveZones(points);
    final overall = overallState(zones);
    final latest = store.actionOrder.isNotEmpty ? store.actions[store.actionOrder.first] : null;

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('The house, right now',
                            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
                        const SizedBox(height: 4),
                        Wrap(
                          crossAxisAlignment: WrapCrossAlignment.center,
                          spacing: 8,
                          runSpacing: 2,
                          children: [
                            HealthDot(overall),
                            Text(_overallLabel(overall), style: const TextStyle(color: DomoraColors.inkDim, fontSize: 13)),
                            Text('t=${store.now.toString().padLeft(3, '0')}',
                                style: const TextStyle(color: DomoraColors.inkFaint, fontSize: 12, fontFamily: 'monospace')),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: DomoraSpace.s2),
                  DomoraChip(occ.occupied ? 'occupied' : 'empty', state: occ.occupied ? DomoraState.ok : DomoraState.learn),
                ],
              ),
              const SizedBox(height: DomoraSpace.s4),
              Wrap(
                spacing: DomoraSpace.s3,
                runSpacing: DomoraSpace.s3,
                children: [for (final z in zones) _ZoneCard(zone: z)],
              ),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: DomoraSpace.s3,
          mainAxisSpacing: DomoraSpace.s3,
          childAspectRatio: 2.2,
          children: [
            StatTile(label: 'Occupancy', value: occ.occupied ? 'Home' : 'Away', state: occ.occupied ? DomoraState.ok : null),
            StatTile(label: 'Line flow', value: water.flowLpm.toStringAsFixed(2), unit: 'L/min', state: water.leak ? DomoraState.crit : null),
            StatTile(
              label: 'Tank level',
              value: water.levelPct.isNaN ? '—' : '${water.levelPct.toStringAsFixed(0)}%',
              state: (!water.levelPct.isNaN && water.levelPct < 15) ? DomoraState.warn : null,
            ),
            StatTile(
              label: 'Main valve',
              value: water.valveState,
              state: water.valveSuspect ? DomoraState.crit : (water.valveState == 'closed' ? null : DomoraState.ok),
            ),
            StatTile(
              label: 'Pump',
              value: water.pumpState,
              state: (water.pumpSuspect || water.dryrun) ? DomoraState.crit : (water.pumpState == 'on' ? DomoraState.ok : null),
            ),
            StatTile(label: 'Power draw', value: powerW.isNaN ? '—' : powerW.toStringAsFixed(0), unit: powerW.isNaN ? null : 'W'),
          ],
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('THE HOUSE IS THINKING', style: TextStyle(fontSize: 12, letterSpacing: 0.6, color: DomoraColors.inkFaint, fontWeight: FontWeight.w700)),
              const SizedBox(height: DomoraSpace.s2),
              if (latest == null)
                const Text('No autonomous action yet — the house is watching.', style: TextStyle(color: DomoraColors.inkFaint, fontStyle: FontStyle.italic))
              else
                _ActionLine(action: latest),
            ],
          ),
        ),
      ],
    );
  }

  String _overallLabel(DomoraState s) => switch (s) {
        DomoraState.ok => 'Nominal',
        DomoraState.warn => 'Attention',
        DomoraState.crit => 'Critical',
        DomoraState.learn => 'Learning',
        DomoraState.pred => 'Predicting',
      };
}

class _ZoneCard extends StatelessWidget {
  final Zone zone;
  const _ZoneCard({required this.zone});

  @override
  Widget build(BuildContext context) {
    final color = DomoraColors.forState(zone.state);
    // Click-through to the room detail page, same entry point Studio uses.
    return InkWell(
      onTap: () => pushScoped(context, RoomScreen(id: zone.id)),
      borderRadius: BorderRadius.circular(DomoraRadius.r1),
      child: _card(color),
    );
  }

  Widget _card(Color color) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(DomoraSpace.s3),
      decoration: BoxDecoration(
        color: DomoraColors.bg2,
        borderRadius: BorderRadius.circular(DomoraRadius.r1),
        border: Border.all(color: zone.state == DomoraState.ok ? DomoraColors.line : color.withValues(alpha: 0.5)),
        boxShadow: zone.state == DomoraState.crit ? [BoxShadow(color: color.withValues(alpha: 0.3), blurRadius: 16)] : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          HealthDot(zone.state),
          const SizedBox(height: 8),
          Text(zone.label, style: const TextStyle(fontWeight: FontWeight.w600, color: DomoraColors.ink, fontSize: 13)),
          Text(zone.detail, style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkFaint)),
        ],
      ),
    );
  }
}

class _ActionLine extends StatelessWidget {
  final ActionCard action;
  const _ActionLine({required this.action});

  @override
  Widget build(BuildContext context) {
    final state = switch (action.status) {
      'confirmed' => DomoraState.ok,
      'failed' => DomoraState.crit,
      _ => DomoraState.learn,
    };
    final label = switch (action.status) {
      'confirmed' => 'verified',
      'failed' => 'escalated',
      _ => 'pending',
    };
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 8,
      runSpacing: 4,
      children: [
        Text(action.cause ?? 'action #${action.id}', style: const TextStyle(fontWeight: FontWeight.w600, color: DomoraColors.ink)),
        const Text('→', style: TextStyle(color: DomoraColors.inkFaint)),
        Text(action.expect ?? action.command ?? '', style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkDim)),
        DomoraChip(label, state: state),
      ],
    );
  }
}
