// Shared test scaffolding. Every fixture under test/fixtures/ is a real
// response captured from a live hub in this repo (curled from a running
// `hub.services.api`), never hand-written JSON — the same discipline the
// Studio build used. Responses are served back as raw bytes so the widget
// under test parses exactly what the server sent.
import 'dart:convert';
import 'dart:io';

import 'package:domora_mobile/core/app_scope.dart';
import 'package:domora_mobile/core/hub_client.dart';
import 'package:domora_mobile/core/store.dart';
import 'package:domora_mobile/theme/tokens.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

List<Map<String, dynamic>> loadFrames(String name) {
  final raw = File('test/fixtures/$name').readAsStringSync();
  return (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
}

Map<String, dynamic> loadJson(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync()) as Map<String, dynamic>;

void feed(DomoraStore store, List<Map<String, dynamic>> frames) {
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

/// A HubClient whose HTTP side replays real captured endpoint bodies.
/// Anything not in [routes] 404s — which is exactly what a hub without
/// `--playback` does for /history and /playback.json, so the honest
/// "no journal" fallbacks get exercised rather than mocked away.
HubClient mockHub(DomoraStore store, {Map<String, String> routes = const {}}) {
  final client = MockClient((request) async {
    final path = request.url.path;
    final file = routes[path];
    if (file == null) {
      return http.Response('{"error":"not found"}', 404, headers: {'content-type': 'application/json'});
    }
    return http.Response.bytes(
      File('test/fixtures/$file').readAsBytesSync(),
      200,
      headers: {'content-type': 'application/json'},
    );
  });
  return HubClient(baseUrl: '127.0.0.1:8080', store: store, httpClient: client);
}

/// Wraps a screen exactly the way the running app does: the store/hub scopes
/// AppShell provides, a Navigator so pushScoped() drill-downs work, and a
/// Scaffold — tab screens are rendered inside AppShell's Scaffold body, and
/// InkWell-based rows need that Material ancestor. Pass `scaffold: false` for
/// the detail screens that build their own Scaffold, so the test doesn't see
/// two app bars.
Widget harness(DomoraStore store, HubClient client, Widget child, {bool scaffold = true}) => MaterialApp(
      theme: domoraDarkTheme(),
      home: StoreScope(
        store: store,
        child: HubScope(client: client, child: scaffold ? Scaffold(body: child) : child),
      ),
    );

/// Screens are long scrolling ListViews; the default 800px test surface would
/// leave lower cards unmounted (a ListView only realizes what's in view).
/// Give the surface room for the whole screen instead of asserting through a
/// scroll — simpler, and just as real.
Size get tallSurface => const Size(420, 2600);
