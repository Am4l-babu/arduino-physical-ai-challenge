// Phase D — Room / Appliance / Sensor detail pages, plus the click-through
// that reaches them. Driven by the same real captured hub data as the
// dashboards: `stuck`-scenario /ws frames and a real /nilm body.
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/screens/appliance.dart';
import 'package:domora_mobile/screens/home.dart';
import 'package:domora_mobile/screens/room.dart';
import 'package:domora_mobile/screens/sensor.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  Future<void> useTallSurface(WidgetTester tester) async {
    tester.view.physicalSize = tallSurface;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
  }

  group('Room', () {
    testWidgets('Utility shows the real water points and the real action', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      await tester.pumpWidget(
          harness(store, mockHub(store), const RoomScreen(id: 'utility'), scaffold: false));
      await tester.pump();

      expect(find.text('leak suspected'), findsWidgets);
      expect(find.text('main_valve.valve_state'), findsOneWidget);
      expect(find.text('health.main_valve'), findsOneWidget);
      expect(find.text('suspect'), findsOneWidget,
          reason: 'the real health point value from the captured run');
      expect(find.text('leak:main_line'), findsOneWidget);
      expect(find.text('escalated'), findsOneWidget);
    });

    testWidgets('Living is explicit that nothing acts on it', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      await tester.pumpWidget(
          harness(store, mockHub(store), const RoomScreen(id: 'living'), scaffold: false));
      await tester.pump();

      expect(find.textContaining('only the water loop (utility) is autonomous today'), findsOneWidget);
    });

    testWidgets('an unknown room id says so instead of rendering an empty page', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();

      await tester.pumpWidget(
          harness(store, mockHub(store), const RoomScreen(id: 'garage'), scaffold: false));
      await tester.pump();

      expect(find.textContaining('No zone named "garage"'), findsOneWidget);
    });
  });

  group('Appliance', () {
    testWidgets('renders the real kettle ledger entry and refuses to invent health numbers',
        (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store, routes: {'/nilm': 'nilm.json'});

      await tester.pumpWidget(
          harness(store, client, const ApplianceScreen(name: 'kettle'), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.text('7.50 Wh'), findsOneWidget, reason: 'real energy from the captured ledger');
      expect(find.text('signature 1.80 kW'), findsOneWidget,
          reason: 'the real cluster mean_w (1800), through the app-wide watt formatter');
      expect(find.text('2'), findsWidgets, reason: 'the real on/off event count');
      expect(find.text('Health score'), findsOneWidget);
      expect(find.text('not computed'), findsNWidgets(4),
          reason: 'health/RUL/failure-probability/vibration are stated as not computed, never faked');
    });

    testWidgets('an appliance missing from the real ledger says so', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store, routes: {'/nilm': 'nilm.json'});

      await tester.pumpWidget(
          harness(store, client, const ApplianceScreen(name: 'dishwasher'), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.textContaining('No appliance named "dishwasher"'), findsOneWidget);
    });
  });

  group('Sensor', () {
    testWidgets('a numeric point gets a value, source, confidence and a raw table', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      await tester.pumpWidget(harness(
          store, mockHub(store), const SensorScreen(pointKey: 'water_tank.level_pct'),
          scaffold: false));
      await tester.pump();
      await tester.pump();

      expect(find.text('fp2'), findsOneWidget, reason: 'the real source node id from the captured run');
      expect(find.text('Recent raw values'), findsOneWidget);
      expect(find.text('No history recorded yet.'), findsNothing);
    });

    testWidgets('a non-numeric point gets no fabricated trend', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      await tester.pumpWidget(harness(
          store, mockHub(store), const SensorScreen(pointKey: 'main_valve.valve_state'),
          scaffold: false));
      await tester.pump();
      await tester.pump();

      expect(find.text('Trend'), findsNothing, reason: 'a string point has no trend to draw');
      expect(find.textContaining("isn't numeric"), findsOneWidget);
    });

    testWidgets('an unknown point key says so rather than showing zeros', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();

      await tester.pumpWidget(harness(
          store, mockHub(store), const SensorScreen(pointKey: 'kitchen.toaster_temp'),
          scaffold: false));
      await tester.pump();
      await tester.pump();

      expect(find.textContaining('No live data for "kitchen.toaster_temp"'), findsOneWidget);
    });
  });

  testWidgets('tapping a Home zone card drills into that real room', (tester) async {
    await useTallSurface(tester);
    final store = DomoraStore();
    feed(store, loadFrames('stuck_frames.json'));

    await tester.pumpWidget(harness(store, mockHub(store), const HomeScreen()));
    await tester.pump();

    await tester.tap(find.text('Water / Utility'));
    await tester.pumpAndSettle();

    // now on the Room page: its points list is the giveaway
    expect(find.text('Points in this room'), findsOneWidget);
    expect(find.text('virtual.water.leak_suspected'), findsOneWidget);
  });
}
