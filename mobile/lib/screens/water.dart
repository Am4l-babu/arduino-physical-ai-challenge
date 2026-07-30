// Phase C — Water dashboard. Port of studio/screens/water.js. Flow, tank
// level, valve/pump state, leak + dry-run status, and the real incident list
// (the flagship leak loop and the dry-run protection loop) straight from the
// live action ledger — the same data History replays, so no second bespoke
// scrubber is built here.
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
import '../widgets/stat_tile.dart';

const levelKey = 'water_tank.level_pct';
const flowKey = 'tank.line.flow_lpm';

class WaterScreen extends StatefulWidget {
  const WaterScreen({super.key});

  @override
  State<WaterScreen> createState() => _WaterScreenState();
}

class _WaterScreenState extends State<WaterScreen> {
  List<SeriesPoint>? _journalLevel;
  List<SeriesPoint>? _journalFlow;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final client = HubScope.of(context);
    final level = await client.fetchHistory(levelKey);
    final flow = await client.fetchHistory(flowKey);
    if (!mounted) return;
    setState(() {
      if (level != null && level.isNotEmpty) _journalLevel = level;
      if (flow != null && flow.isNotEmpty) _journalFlow = flow;
    });
  }

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return AnimatedBuilder(animation: store, builder: (context, _) => _body(store));
  }

  Widget _body(DomoraStore store) {
    final water = deriveWater(store.points);
    final hasWater = water.valveState != '—' || !water.levelPct.isNaN || water.flowLpm > 0;

    if (!hasWater) {
      return ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: const [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CardTitle('Water'),
                EmptyNote(
                    "This scenario doesn't run the water system. Try --scenario leak, stuck, dryrun, or dryrun_stuck."),
              ],
            ),
          ),
        ],
      );
    }

    final levelSeries = _journalLevel ?? store.seriesFor(levelKey);
    final flowSeries = _journalFlow ?? store.seriesFor(flowKey);

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: DomoraSpace.s3,
          mainAxisSpacing: DomoraSpace.s3,
          childAspectRatio: 2.2,
          children: [
            StatTile(
              label: 'Line flow',
              value: fmtNum(water.flowLpm, 2),
              unit: 'L/min',
              state: water.leak ? DomoraState.crit : null,
            ),
            StatTile(
              label: 'Tank level',
              value: fmtPct(water.levelPct),
              state: (!water.levelPct.isNaN && water.levelPct < 15) ? DomoraState.warn : null,
            ),
            StatTile(
              label: 'Main valve',
              value: water.valveState,
              state: water.valveSuspect ? DomoraState.crit : null,
            ),
            StatTile(
              label: 'Pump',
              value: water.pumpState,
              state: (water.pumpSuspect || water.dryrun) ? DomoraState.crit : null,
            ),
          ],
        ),
        const SizedBox(height: DomoraSpace.s3),
        Wrap(
          spacing: DomoraSpace.s2,
          runSpacing: DomoraSpace.s2,
          children: [
            DomoraChip(water.leak ? 'leak suspected' : 'no leak',
                state: water.leak ? DomoraState.crit : DomoraState.ok),
            DomoraChip(water.dryrun ? 'pump dry-run suspected' : 'pump nominal',
                state: water.dryrun ? DomoraState.crit : DomoraState.ok),
            DomoraChip(water.valveSuspect ? 'valve suspect' : 'valve trusted',
                state: water.valveSuspect ? DomoraState.crit : DomoraState.ok),
          ],
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Tank level — this session'),
              DomoraLineChart(data: levelSeries, unit: '%', valueFmt: (v) => v.toStringAsFixed(0)),
              if (_journalLevel != null) const _ChartNote(),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Line flow — this session'),
              DomoraLineChart(data: flowSeries, unit: ' L/min', valueFmt: (v) => v.toStringAsFixed(2)),
              if (_journalFlow != null) const _ChartNote(),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Incidents — cause → evidence → command → verify'),
              if (store.actionOrder.isEmpty)
                const EmptyNote('No autonomous action yet in this run.')
              else
                for (final id in store.actionOrder) IncidentRow(action: store.actions[id]!),
            ],
          ),
        ),
      ],
    );
  }
}

class _ChartNote extends StatelessWidget {
  const _ChartNote();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.only(top: DomoraSpace.s1),
        child: Text('Journal-backed (recorded run).',
            style: TextStyle(fontSize: 11, color: DomoraColors.inkFaint)),
      );
}
