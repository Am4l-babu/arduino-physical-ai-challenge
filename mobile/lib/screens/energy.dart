// Phase C — Energy dashboard. Port of studio/screens/energy.js. Live power
// from the /ws twin points plus the real NILM ledger from GET /nilm (the
// server's own authoritative hub/agents/energy.py report — see core/nilm.dart
// for why it isn't rebuilt client-side), and a trend chart that is
// journal-backed when the hub runs with --playback and falls back to the
// live session buffer otherwise. No fabricated thresholds or forecasts.
import 'dart:async';

import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/hub_client.dart';
import '../core/nilm.dart';
import '../core/store.dart';
import '../core/twin.dart';
import '../theme/tokens.dart';
import '../widgets/bar_chart.dart';
import '../widgets/glass_card.dart';
import '../widgets/incident_row.dart';
import '../widgets/line_chart.dart';
import '../widgets/stat_tile.dart';
import 'appliance.dart';

const powerKey = 'main_panel.power_w';
const _nilmPoll = Duration(seconds: 2);

class EnergyScreen extends StatefulWidget {
  const EnergyScreen({super.key});

  @override
  State<EnergyScreen> createState() => _EnergyScreenState();
}

class _EnergyScreenState extends State<EnergyScreen> {
  List<SeriesPoint>? _journalSeries; // null = not loaded / no journal this run
  NilmReport? _nilm;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final client = HubScope.of(context);
    final series = await client.fetchHistory(powerKey);
    if (mounted && series != null && series.isNotEmpty) setState(() => _journalSeries = series);
    await _pollNilm(client);
    _poll = Timer.periodic(_nilmPoll, (_) => _pollNilm(client));
  }

  Future<void> _pollNilm(HubClient client) async {
    final report = parseNilm(await client.fetchNilm());
    if (mounted && report != null) setState(() => _nilm = report);
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return AnimatedBuilder(animation: store, builder: (context, _) => _body(store));
  }

  Widget _body(DomoraStore store) {
    final powerW = derivePowerW(store.points);
    final ledger = _nilm?.ledger ?? const <NilmEntry>[];
    final series = (_journalSeries != null && _journalSeries!.isNotEmpty)
        ? _journalSeries!
        : store.seriesFor(powerKey);

    if (powerW.isNaN && ledger.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: const [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CardTitle('Energy'),
                EmptyNote(
                    "This scenario doesn't report whole-house power. Run the hub with --scenario energy to see this dashboard live."),
              ],
            ),
          ),
        ],
      );
    }

    final peak = series.isNotEmpty
        ? series.map((p) => p.value).reduce((a, b) => a > b ? a : b)
        : powerW;
    final nearPeak = !powerW.isNaN && peak > 0 && powerW >= peak * 0.9;

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 3,
          crossAxisSpacing: DomoraSpace.s2,
          mainAxisSpacing: DomoraSpace.s2,
          childAspectRatio: 1.15, // 3-up tiles need the height for label + value
          children: [
            StatTile(label: 'Power now', value: fmtWatts(powerW), state: nearPeak ? DomoraState.warn : null),
            StatTile(label: 'Session peak', value: series.isNotEmpty ? fmtWatts(peak) : '—'),
            StatTile(label: 'Appliances', value: '${ledger.length}'),
          ],
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Power — this session'),
              DomoraLineChart(data: series, unit: ' W', valueFmt: (v) => v.toStringAsFixed(0)),
              if (_journalSeries != null) const _ChartNote(),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('NILM appliance breakdown'),
              if (ledger.isNotEmpty)
                DomoraBarChart(
                  items: [for (final a in ledger) BarItem(a.name, a.energyWh)],
                  unit: ' Wh',
                  onItemTap: (item) => pushScoped(context, ApplianceScreen(name: item.label)),
                )
              else
                const EmptyNote(
                    'No appliance edges detected yet — the disaggregator needs a device to switch on/off.'),
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
