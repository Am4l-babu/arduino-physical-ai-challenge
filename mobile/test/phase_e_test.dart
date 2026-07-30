// Phase E — History (journal scrubbing), AI Insights, Settings, and Search.
// Real captured data throughout: a real /playback.json built from an actual
// recorded `stuck` journal, a real /graph body from hub/config/house.json,
// and the real /nilm ledger.
import 'package:domora_mobile/core/app_scope.dart';
import 'package:domora_mobile/core/insights.dart';
import 'package:domora_mobile/core/nilm.dart';
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/screens/history.dart';
import 'package:domora_mobile/screens/insights.dart';
import 'package:domora_mobile/screens/search.dart';
import 'package:domora_mobile/screens/settings.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  Future<void> useTallSurface(WidgetTester tester) async {
    tester.view.physicalSize = const Size(420, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
  }

  group('History', () {
    testWidgets('lands on the resolved end-state of a real recorded run', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store, routes: {'/playback.json': 'playback.json'});

      await tester.pumpWidget(harness(store, client, const HistoryScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.text('t=119 / t=119'), findsOneWidget);
      expect(find.text('leak:main_line'), findsOneWidget);
      expect(find.text('escalated'), findsOneWidget);
    });

    testWidgets('scrubbing back to t=0 shows a house with no incident yet', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store, routes: {'/playback.json': 'playback.json'});

      await tester.pumpWidget(harness(store, client, const HistoryScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }
      expect(find.text('escalated'), findsOneWidget); // precondition: it IS there at the end

      // drag the scrubber to its minimum — the same gesture a user makes
      await tester.drag(find.byType(Slider), const Offset(-2000, 0));
      await tester.pump();

      expect(find.text('t=000 / t=119'), findsOneWidget);
      expect(find.text('No action dispatched yet at this tick.'), findsOneWidget);
      expect(find.text('escalated'), findsNothing,
          reason: 'the scrub must be time-aware — the incident had not happened at t=0');
    });

    testWidgets('a hub with no journal says how to record one instead of faking history',
        (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store); // /playback.json 404s, as a live hub does

      await tester.pumpWidget(harness(store, client, const HistoryScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.textContaining('No recorded journal for this run'), findsOneWidget);
      expect(find.textContaining('--journal demo.db'), findsOneWidget);
    });
  });

  group('Insights', () {
    test('derives the real critical/warning cards from a real captured run', () {
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      final nilm = parseNilm(loadJson('nilm.json'))!.ledger;

      final cards = deriveInsights(store, nilm);
      final ids = cards.map((c) => c.id).toList();

      expect(ids, contains('leak'));
      expect(ids, contains('health-main_valve'));
      expect(ids, contains('action-failed-1'));
      expect(ids, contains('nilm-top'));
      // priority ordering: every critical precedes every warning precedes info
      final priorities = cards.map((c) => c.priority.index).toList();
      final sorted = [...priorities]..sort();
      expect(priorities, sorted);
      expect(cards.first.priority, InsightPriority.critical);
    });

    test('a nominal house gets one honest "nothing to flag" card, not an empty screen', () {
      final cards = deriveInsights(DomoraStore(), const []);
      expect(cards, hasLength(1));
      expect(cards.first.id, 'nominal');
    });

    testWidgets('renders the real leak card with its real evidence', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      final client = mockHub(store, routes: {'/nilm': 'nilm.json'});

      await tester.pumpWidget(harness(store, client, const InsightsScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.textContaining('Leak suspected on the main line'), findsOneWidget);
      expect(find.textContaining('kettle used the most energy'), findsOneWidget);
      expect(find.text('critical'), findsWidgets);
    });
  });

  group('Settings', () {
    testWidgets('lists the real house graph assets', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      final client = mockHub(store, routes: {'/graph': 'graph.json'});

      await tester.pumpWidget(harness(store, client, const SettingsScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.text('main_valve'), findsOneWidget, reason: 'a real asset from hub/config/house.json');
      expect(find.text('water_tank'), findsOneWidget);
      expect(find.text('open, close'), findsOneWidget, reason: "the valve's real command list");
      expect(find.textContaining('No accounts, roles, or login'), findsOneWidget);
    });

    testWidgets('a server without /graph says so rather than showing an empty house', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();

      await tester.pumpWidget(
          harness(store, mockHub(store), const SettingsScreen(), scaffold: false));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.text('House graph not available from this server.'), findsWidgets);
    });
  });

  group('Search', () {
    test('an empty query offers screens and rooms but not the long point list', () {
      final results = searchResults('', ['main_valve.valve_state', 'house.occupied']);
      expect(results.any((r) => r.hint == 'point'), isFalse);
      expect(results.any((r) => r.label == 'Energy'), isTrue);
      expect(results.any((r) => r.label == 'Room: Living'), isTrue);
    });

    test('a query matches real live point keys', () {
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      final results = searchResults('valve', store.points.keys);
      final points = results.where((r) => r.hint == 'point').map((r) => r.label).toList();
      expect(points, contains('main_valve.valve_state'));
      expect(points, contains('health.main_valve'));
    });

    test('no result can actuate anything — every target is a destination', () {
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));
      for (final r in searchResults('valve', store.points.keys)) {
        expect(r.tab != null || r.roomId != null || r.pointKey != null || r.menu != null, isTrue,
            reason: 'search is navigate-only: safety.py\'s capability table is the sole actuation path');
      }
    });

    testWidgets('picking a real point pops that point back to the shell', (tester) async {
      await useTallSurface(tester);
      final store = DomoraStore();
      feed(store, loadFrames('stuck_frames.json'));

      SearchTarget? picked;
      await tester.pumpWidget(harness(
        store,
        mockHub(store),
        Builder(
          builder: (context) => TextButton(
            // the same call AppShell's search button makes
            onPressed: () async {
              picked = await pushScoped<SearchTarget>(context, const SearchScreen());
            },
            child: const Text('open'),
          ),
        ),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'valve_state');
      await tester.pumpAndSettle();
      await tester.tap(find.text('main_valve.valve_state'));
      await tester.pumpAndSettle();

      expect(picked?.pointKey, 'main_valve.valve_state');
    });
  });
}
