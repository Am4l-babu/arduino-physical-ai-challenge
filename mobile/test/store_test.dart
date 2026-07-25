// Feeds the real store.dart port with actual captured /ws frames from a
// live hub run (the same stuck_frames.json used to verify Studio's web
// build — see docs/APP_PLAN.md, PROGRESS.md). Not hand-written fixtures.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:domora_mobile/core/store.dart';

List<Map<String, dynamic>> _loadFrames(String name) {
  final raw = File('test/fixtures/$name').readAsStringSync();
  return (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
}

void _feed(DomoraStore store, List<Map<String, dynamic>> frames) {
  for (final f in frames) {
    switch (f['type']) {
      case 'snapshot':
        store.applySnapshot(f);
      case 'point':
        store.applyPoint(f);
      case 'event':
        store.applyEvent(f);
    }
  }
}

void main() {
  test('real stuck-scenario frames drive the store to the real leak/escalation state', () {
    final store = DomoraStore();
    _feed(store, _loadFrames('stuck_frames.json'));

    expect(store.point('virtual.water.leak_suspected'), true);
    expect(store.point('health.main_valve'), 'suspect');
    expect(store.actionOrder, isNotEmpty);

    final action = store.actions[store.actionOrder.first]!;
    expect(action.cause, 'leak:main_line');
    expect(action.status, 'failed', reason: 'the stuck valve never confirms — the flagship escalation path');
  });

  test('series buffer only tracks numeric points, bounded, real values', () {
    final store = DomoraStore();
    _feed(store, _loadFrames('stuck_frames.json'));

    final levelSeries = store.seriesFor('water_tank.level_pct');
    expect(levelSeries, isNotEmpty);
    expect(levelSeries.every((p) => p.value > 0 && p.value < 100), true);

    // a boolean point must never leak into the numeric series buffer
    expect(store.seriesFor('virtual.water.leak_suspected'), isEmpty);
  });

  test('real energy-scenario frames recover the kettle event pair', () {
    final store = DomoraStore();
    _feed(store, _loadFrames('energy_frames.json'));

    final power = store.seriesFor('main_panel.power_w');
    expect(power.length, greaterThan(50));
  });

  test('reset clears everything', () {
    final store = DomoraStore();
    _feed(store, _loadFrames('stuck_frames.json'));
    store.reset();

    expect(store.points, isEmpty);
    expect(store.series, isEmpty);
    expect(store.actions, isEmpty);
    expect(store.now, 0);
  });
}
