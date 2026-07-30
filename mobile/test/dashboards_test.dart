// Phase C — Energy / Water / Security, driven by real captured hub data:
// the `energy` scenario's /ws frames + its real /nilm ledger, and the `stuck`
// scenario's frames (the flagship leak → failed-verification escalation).
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/screens/energy.dart';
import 'package:domora_mobile/screens/security.dart';
import 'package:domora_mobile/screens/water.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  Future<void> useTallSurface(WidgetTester tester) async {
    tester.view.physicalSize = tallSurface;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
  }

  group('Energy', () {
    testWidgets('renders the real NILM ledger from a real /nilm body', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('energy_frames.json'));
      final client = mockHub(store, routes: {'/nilm': 'nilm.json'});

      await tester.pumpWidget(harness(store, client, const EnergyScreen()));
      // the screen's post-frame load awaits /history then /nilm; each await is
      // its own microtask hop, so pump until both have landed
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      // the true values from the captured ledger — kettle 7.495 Wh
      expect(find.text('kettle'), findsOneWidget);
      expect(find.text('7.50 Wh'), findsOneWidget,
          reason: 'the real disaggregated kettle energy, not a rounded placeholder');
      expect(find.text('3'), findsWidgets, reason: '3 appliances tracked in the captured ledger');
    });

    testWidgets('says so honestly when a scenario reports no power and no NILM', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore(); // empty: no power point, no ledger
      final client = mockHub(store); // /nilm 404s, as a non-energy hub would

      await tester.pumpWidget(harness(store, client, const EnergyScreen()));
      await tester.pump();
      await tester.pump();

      expect(find.textContaining("doesn't report whole-house power"), findsOneWidget);
    });
  });

  group('Water', () {
    testWidgets('renders the real leak escalation with its real reason', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      final client = mockHub(store); // no journal → live session buffer, honest fallback

      await tester.pumpWidget(harness(store, client, const WaterScreen()));
      await tester.pump();
      await tester.pump();

      expect(find.text('leak suspected'), findsOneWidget);
      expect(find.text('valve suspect'), findsOneWidget);
      expect(find.text('leak:main_line'), findsOneWidget);
      expect(find.text('escalated'), findsOneWidget);
      expect(find.textContaining('actuation unverified'), findsOneWidget,
          reason: 'the incident row must show the hub\'s real escalation reason');
      expect(find.text('command: domora/cmd/main_valve/close'), findsOneWidget);
      expect(find.text('Journal-backed (recorded run).'), findsNothing,
          reason: 'no --playback journal here, so it must not claim to be journal-backed');
    });

    testWidgets('labels the chart journal-backed only when a real /history answers', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      // a real /history body, captured from a real --playback server
      final client = mockHub(store, routes: {'/history': 'history_level.json'});

      await tester.pumpWidget(harness(store, client, const WaterScreen()));
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.text('Journal-backed (recorded run).'), findsNWidgets(2),
          reason: 'both trend charts fell back to the real journal series');
    });

    testWidgets('says so honestly when a scenario runs no water system', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store);

      await tester.pumpWidget(harness(store, client, const WaterScreen()));
      await tester.pump();
      await tester.pump();

      expect(find.textContaining("doesn't run the water system"), findsOneWidget);
    });
  });

  group('Security', () {
    testWidgets('shows the real alert feed and is honest about unconnected sensors', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      final client = mockHub(store);

      await tester.pumpWidget(harness(store, client, const SecurityScreen()));
      await tester.pump();

      expect(find.text('domora/alert/critical'), findsOneWidget,
          reason: 'the real escalation alert from the captured run');
      expect(find.text('Doors / windows'), findsOneWidget);
      expect(find.text('Smoke'), findsOneWidget);
      expect(find.text('no node reporting this yet'), findsNWidgets(5),
          reason: 'five sensor classes with no data source — stated, never faked');
    });

    testWidgets('reports no alerts rather than inventing one on a quiet run', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store);

      await tester.pumpWidget(harness(store, client, const SecurityScreen()));
      await tester.pump();

      expect(find.text('No alerts in this run.'), findsOneWidget);
      expect(find.text('empty'), findsOneWidget, reason: 'no occupancy data = empty, not a fabricated presence');
    });
  });
}
