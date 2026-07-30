// Phase D — Appliance detail. Port of studio/screens/appliance.js. Data is
// the real GET /nilm report (hub/agents/energy.py's own ledger). Health
// score, remaining useful life, failure probability, and sound/vibration
// analysis are NOT computed anywhere in this codebase — this page says so
// rather than inventing numbers. See docs/APP_PLAN.md §7.
import 'dart:async';

import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/nilm.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/incident_row.dart';
import '../widgets/stat_tile.dart';

const _poll = Duration(seconds: 2);

const _notComputed = [
  'Health score',
  'Remaining useful life',
  'Failure probability',
  'Sound / vibration analysis',
];

class ApplianceScreen extends StatefulWidget {
  final String name;
  const ApplianceScreen({super.key, required this.name});

  @override
  State<ApplianceScreen> createState() => _ApplianceScreenState();
}

class _ApplianceScreenState extends State<ApplianceScreen> {
  NilmReport? _report;
  bool _loaded = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _load();
      _timer = Timer.periodic(_poll, (_) => _load());
    });
  }

  Future<void> _load() async {
    final report = parseNilm(await HubScope.of(context).fetchNilm());
    if (!mounted) return;
    setState(() {
      _report = report;
      _loaded = true;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.name)),
      body: _body(),
    );
  }

  Widget _body() {
    final report = _report;
    if (report == null) {
      return ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Appliance'),
                EmptyNote(_loaded
                    ? "No NILM data available — this scenario doesn't run the panel CT, or the hub isn't reachable."
                    : 'Loading…'),
              ],
            ),
          ),
        ],
      );
    }

    final cluster = report.clusterFor(widget.name);
    final energyWh = report.energyWh[widget.name];

    if (cluster == null && energyWh == null) {
      return ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Appliance'),
                EmptyNote('No appliance named "${widget.name}" in the current NILM ledger.'),
              ],
            ),
          ),
        ],
      );
    }

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(widget.name,
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
              const SizedBox(height: 2),
              Text(cluster != null ? 'signature ${fmtWatts(cluster.meanW)}' : 'signature unknown',
                  style: const TextStyle(fontSize: 13, color: DomoraColors.inkFaint)),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 3,
          crossAxisSpacing: DomoraSpace.s2,
          mainAxisSpacing: DomoraSpace.s2,
          childAspectRatio: 1.0, // labels here wrap to two lines ("Energy this run")
          children: [
            StatTile(
                label: 'Energy this run',
                value: energyWh != null ? '${energyWh.toStringAsFixed(2)} Wh' : '—'),
            StatTile(label: 'Signature power', value: cluster != null ? fmtWatts(cluster.meanW) : '—'),
            StatTile(label: 'On/off events', value: cluster != null ? '${cluster.events}' : '—'),
          ],
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Not computed'),
              for (final label in _notComputed) _NotComputedRow(label: label),
              const SizedBox(height: DomoraSpace.s2),
              const Text(
                "This system disaggregates appliances from the panel's aggregate power alone (NILM). It doesn't "
                'have per-appliance current, sound, or vibration sensors, so it has no basis to compute these — '
                'showing a number here would be invented, not measured.',
                style: TextStyle(fontSize: 12, color: DomoraColors.inkFaint, height: 1.4),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _NotComputedRow extends StatelessWidget {
  final String label;
  const _NotComputedRow({required this.label});

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
            const Text('not computed',
                style: TextStyle(fontSize: 11, color: DomoraColors.inkFaint, fontStyle: FontStyle.italic)),
          ],
        ),
      );
}
