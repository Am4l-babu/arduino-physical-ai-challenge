// Widget test: pumps the real HomeScreen against the real store, fed with
// real captured hub frames — same discipline as the web Studio's headless
// DOM-shim verification, but as a first-class flutter_test widget test.
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/screens/home.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  // Home is a scrolling ListView; the default 800px test surface leaves the
  // "thinking strip" card unmounted (ListView only realizes children within
  // the viewport). Give the test surface room for the whole screen instead
  // of asserting through a scroll — simpler and just as real.
  Future<void> useTallSurface(WidgetTester tester) async {
    tester.view.physicalSize = tallSurface;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
  }

  testWidgets('Home renders the real leak/valve-suspect escalation as critical', (tester) async {
    await useTallSurface(tester);
    final store = DomoraStore();
    feed(store, loadFrames('stuck_frames.json'));

    await tester.pumpWidget(harness(store, mockHub(store), const HomeScreen()));
    await tester.pump();

    expect(find.text('Water / Utility'), findsOneWidget);
    expect(find.text('leak suspected'), findsOneWidget, reason: 'the zone detail must show the real leak state, not a placeholder');
    expect(find.text('escalated'), findsOneWidget, reason: 'the failed action must render as escalated');
    expect(find.text('leak:main_line'), findsOneWidget, reason: 'the real action cause must appear in the thinking strip');
  });

  testWidgets('Home renders a nominal empty-store state without crashing', (tester) async {
    await useTallSurface(tester);
    final store = DomoraStore();

    await tester.pumpWidget(harness(store, mockHub(store), const HomeScreen()));
    await tester.pump();

    expect(find.text('No autonomous action yet — the house is watching.'), findsOneWidget);
    expect(find.text('Nominal'), findsOneWidget);
    // an empty house is nominal, not "learning" — regression guard for the
    // exact bug found and fixed in studio/core/twin.js during the web build
    expect(find.text('Learning'), findsNothing);
  });
}
