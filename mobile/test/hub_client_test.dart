// HubClient's HTTP layer, tested with http.testing.MockClient fed REAL
// response bodies captured from an actual running hub (POST /ai on
// 127.0.0.1:8080, this session — see PROGRESS.md) rather than invented JSON.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:domora_mobile/core/hub_client.dart';
import 'package:domora_mobile/core/store.dart';

// Captured verbatim via curl -X POST http://127.0.0.1:8080/ai against a
// live "stuck" scenario hub, both sides of the leak-suspected state.
const _realLeakFalseBody =
    '{"text": "No leak suspected right now. Main valve is open.", "evidence": {"leak_suspected": false, "valve_state": "open"}, "intent": "leak"}';

// json.dumps() defaults to ensure_ascii=True (see hub/services/api.py's
// dumps()), so the real wire bytes escape non-ASCII as \uXXXX rather than
// sending raw UTF-8 — these fixtures match that literally, not a "prettied
// up" re-typing of the text.
const _realLeakTrueBody =
    '{"text": "Yes \\u2014 a leak is suspected: 1.93 L/min flowing with 0 fixtures open and nobody home, persistent for 26 ticks. Main valve is currently open.", '
    '"evidence": {"leak_suspected": true, "valve_state": "open", "flow_lpm": 1.93, "fixtures_open": 0, "occupied": false, "persisted_ticks": 26}, "intent": "leak"}';

const _realUnknownBody =
    '{"text": "I don\'t have data to answer that yet \\u2014 try asking about power, water, leaks, appliance health, what changed while you were away, or the house\'s overall status.", "evidence": {}, "intent": "unknown"}';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('connection state without ever touching the network', () {
    // The app now opens before any address is known (see main.dart /
    // docs/APP_PLAN.md §9) — these paths must be entirely synchronous and
    // network-free, unlike every other test in this file which deliberately
    // never calls connect()/reconnectTo() with a real address either (a
    // genuine WebSocket attempt has no place in this suite).

    test('connect() with no address set reports unconfigured, not connecting', () {
      final store = DomoraStore();
      final client = HubClient(baseUrl: '', store: store);

      client.connect();

      expect(store.connection, 'unconfigured',
          reason: 'no dial is happening, so "connecting" would be a lie');
      client.dispose();
    });

    test('reconnectTo("") degrades back to unconfigured rather than looping on nothing', () {
      final store = DomoraStore();
      final client = HubClient(baseUrl: 'stale.example:1', store: store);

      client.reconnectTo('');

      expect(client.baseUrl, '');
      expect(store.connection, 'unconfigured');
      client.dispose();
    });

    test('reconnectTo() clears stale points from whatever hub was connected before', () {
      final store = DomoraStore();
      store.applyPoint({'key': 'house.occupied', 'value': true, 't': 5});
      expect(store.points, isNotEmpty); // precondition

      final client = HubClient(baseUrl: 'old-house.example:8080', store: store);
      client.reconnectTo('');

      expect(store.points, isEmpty,
          reason: 'a different hub (or none) must not inherit the previous one\'s state');
      client.dispose();
    });
  });

  group('saved hub address (shared_preferences) — Settings reads/writes this', () {
    test('loadSavedAddress returns null on a first-ever launch', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await HubClient.loadSavedAddress(), isNull);
    });

    test('saveAddress persists exactly what loadSavedAddress later returns', () async {
      SharedPreferences.setMockInitialValues({});
      await HubClient.saveAddress('192.168.1.5:8080');
      expect(await HubClient.loadSavedAddress(), '192.168.1.5:8080');
    });
  });

  test('askAi parses a real "no leak" response', () async {
    final client = HubClient(
      baseUrl: 'example.test',
      store: DomoraStore(),
      httpClient: MockClient((req) async {
        expect(req.url.path, '/ai');
        expect(jsonDecode(req.body)['message'], 'is there a leak?');
        return http.Response(_realLeakFalseBody, 200, headers: {'content-type': 'application/json'});
      }),
    );

    final result = await client.askAi('is there a leak?');

    expect(result['intent'], 'leak');
    expect(result['evidence']['leak_suspected'], false);
    expect(result['text'], contains('No leak suspected'));
  });

  test('askAi parses a real active-leak response with full evidence', () async {
    final client = HubClient(
      baseUrl: 'example.test',
      store: DomoraStore(),
      httpClient: MockClient((req) async => http.Response(_realLeakTrueBody, 200)),
    );

    final result = await client.askAi('is there a leak?');

    expect(result['intent'], 'leak');
    expect(result['evidence']['leak_suspected'], true);
    expect(result['evidence']['flow_lpm'], 1.93);
    expect(result['evidence']['persisted_ticks'], 26);
  });

  test('askAi parses the real honest-unknown response', () async {
    final client = HubClient(
      baseUrl: 'example.test',
      store: DomoraStore(),
      httpClient: MockClient((req) async => http.Response(_realUnknownBody, 200)),
    );

    final result = await client.askAi('what is the safest temperature for this room?');

    expect(result['intent'], 'unknown');
    expect(result['evidence'], isEmpty);
    expect(result['text'], contains("don't have data"));
  });

  test('fetchNilm returns null (not a crash) on a non-200 response', () async {
    final client = HubClient(
      baseUrl: 'example.test',
      store: DomoraStore(),
      httpClient: MockClient((req) async => http.Response('Not Found', 404)),
    );

    expect(await client.fetchNilm(), isNull);
  });

  test('fetchHistory parses a real /history-shaped body into SeriesPoint list', () async {
    // shape matches hub/services/api.py's _serve_history verbatim
    const body = '{"key": "tank.line.flow_lpm", "points": [[115, 0.0], [116, 0.0], [117, 0.12]]}';
    final client = HubClient(
      baseUrl: 'example.test',
      store: DomoraStore(),
      httpClient: MockClient((req) async {
        expect(req.url.queryParameters['key'], 'tank.line.flow_lpm');
        return http.Response(body, 200);
      }),
    );

    final points = await client.fetchHistory('tank.line.flow_lpm');

    expect(points, isNotNull);
    expect(points!.length, 3);
    expect(points.last.t, 117);
    expect(points.last.value, 0.12);
  });
}
