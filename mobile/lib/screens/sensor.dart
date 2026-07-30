// Phase D — Sensor detail. Port of studio/screens/sensor.js. Fully generic:
// works for any twin point key, because every point in this system carries
// the same {value, t, source, confidence} shape (hub/twin/state.py's Point).
// No calibration UI — nothing in the backend exposes calibration to change,
// so that control would be decorative. See docs/APP_PLAN.md §7.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/store.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';
import '../widgets/incident_row.dart';
import '../widgets/line_chart.dart';
import '../widgets/stat_tile.dart';

const _staleAfter = 15; // matches hub/twin/state.py's STALE_AFTER

class SensorScreen extends StatefulWidget {
  final String pointKey;
  const SensorScreen({super.key, required this.pointKey});

  @override
  State<SensorScreen> createState() => _SensorScreenState();
}

class _SensorScreenState extends State<SensorScreen> {
  List<SeriesPoint>? _journalSeries;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final series = await HubScope.of(context).fetchHistory(widget.pointKey);
    if (mounted && series != null && series.isNotEmpty) setState(() => _journalSeries = series);
  }

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(widget.pointKey, style: const TextStyle(fontSize: 15, fontFamily: 'monospace'))),
      body: AnimatedBuilder(animation: store, builder: (context, _) => _body(store)),
    );
  }

  Widget _body(DomoraStore store) {
    final p = store.points[widget.pointKey];
    if (p == null) {
      return ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Sensor'),
                EmptyNote('No live data for "${widget.pointKey}" yet in this run.'),
              ],
            ),
          ),
        ],
      );
    }

    final age = store.now - p.t;
    final stale = age > _staleAfter;
    final isNumeric = p.value is num;
    final series = isNumeric ? (_journalSeries ?? store.seriesFor(widget.pointKey)) : const <SeriesPoint>[];

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: DomoraChip(stale ? 'stale' : 'live', state: stale ? DomoraState.warn : DomoraState.ok),
        ),
        const SizedBox(height: DomoraSpace.s3),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: DomoraSpace.s3,
          mainAxisSpacing: DomoraSpace.s3,
          childAspectRatio: 2.2,
          children: [
            StatTile(label: 'Value', value: fmtValue(p.value)),
            StatTile(label: 'Source', value: p.source ?? '—'),
            StatTile(label: 'Confidence', value: p.confidence?.toStringAsFixed(2) ?? '—'),
            StatTile(label: 'Age', value: '$age tick${age == 1 ? "" : "s"}'),
          ],
        ),
        if (isNumeric) ...[
          const SizedBox(height: DomoraSpace.s4),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Trend'),
                DomoraLineChart(data: series),
                if (_journalSeries != null)
                  const Padding(
                    padding: EdgeInsets.only(top: DomoraSpace.s1),
                    child: Text('Journal-backed (recorded run).',
                        style: TextStyle(fontSize: 11, color: DomoraColors.inkFaint)),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Recent raw values'),
              if (series.isEmpty)
                EmptyNote(isNumeric
                    ? 'No history recorded yet.'
                    : "This point isn't numeric — no trend/history table to show, just the live value above.")
              else
                _RawTable(rows: series.reversed.take(15).toList()),
            ],
          ),
        ),
      ],
    );
  }
}

class _RawTable extends StatelessWidget {
  final List<SeriesPoint> rows;
  const _RawTable({required this.rows});

  @override
  Widget build(BuildContext context) {
    return Table(
      columnWidths: const {0: FlexColumnWidth(1), 1: FlexColumnWidth(2)},
      children: [
        const TableRow(children: [_HeadCell('t'), _HeadCell('value')]),
        for (final r in rows)
          TableRow(children: [_Cell(fmtTick(r.t)), _Cell(fmtValue(r.value))]),
      ],
    );
  }
}

class _HeadCell extends StatelessWidget {
  final String text;
  const _HeadCell(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(text.toUpperCase(),
            style: const TextStyle(fontSize: 10, letterSpacing: 0.5, color: DomoraColors.inkFaint)),
      );
}

class _Cell extends StatelessWidget {
  final String text;
  const _Cell(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Text(text,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.inkDim)),
      );
}
