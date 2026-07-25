// Widget test for the AI chat screen, driven by a real captured /ai
// response body (MockClient) through the actual HubClient/askAi code path.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:domora_mobile/core/app_scope.dart';
import 'package:domora_mobile/core/hub_client.dart';
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/screens/ai.dart';
import 'package:domora_mobile/theme/tokens.dart';

// Same real captured body used in hub_client_test.dart (see that file for
// why the em dash is written as —, not a literal character: it matches
// the real wire bytes json.dumps's ensure_ascii=True actually sends).
const _realLeakTrueBody =
    '{"text": "Yes \\u2014 a leak is suspected: 1.93 L/min flowing with 0 fixtures open and nobody home, persistent for 26 ticks. Main valve is currently open.", '
    '"evidence": {"leak_suspected": true, "valve_state": "open", "flow_lpm": 1.93, "fixtures_open": 0, "occupied": false, "persisted_ticks": 26}, "intent": "leak"}';

Widget _harness(HubClient client, DomoraStore store) => MaterialApp(
      theme: domoraDarkTheme(),
      home: StoreScope(store: store, child: HubScope(client: client, child: const Scaffold(body: AiScreen()))),
    );

void main() {
  testWidgets('idle state shows the grounded-answers placeholder, not an empty screen', (tester) async {
    final store = DomoraStore();
    final client = HubClient(baseUrl: 'example.test', store: store, httpClient: MockClient((req) async => http.Response('{}', 200)));

    await tester.pumpWidget(_harness(client, store));

    expect(find.textContaining('grounded in the real twin'), findsOneWidget);
  });

  testWidgets('tapping a quick prompt round-trips through the real HubClient and renders both bubbles + evidence', (tester) async {
    final store = DomoraStore();
    final client = HubClient(
      baseUrl: 'example.test',
      store: store,
      httpClient: MockClient((req) async => http.Response(_realLeakTrueBody, 200)),
    );

    await tester.pumpWidget(_harness(client, store));
    await tester.tap(find.text('Is there a leak?'));
    await tester.pumpAndSettle();

    expect(find.text('Is there a leak?'), findsWidgets); // the chip label AND the user bubble
    expect(find.textContaining('a leak is suspected'), findsOneWidget);
    expect(find.text('leak_suspected'), findsOneWidget, reason: 'evidence card must render the real evidence keys');
    expect(find.text('true'), findsOneWidget);
    expect(find.text('1.93'), findsOneWidget);
  });
}
