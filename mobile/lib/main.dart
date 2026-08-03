import 'package:flutter/material.dart';

import 'core/hub_client.dart';
import 'core/store.dart';
import 'screens/app_shell.dart';
import 'theme/tokens.dart';

void main() {
  runApp(const DomoraMobileApp());
}

/// Opens straight into the app — no hub address required up front. A
/// previously-saved address (if any) is loaded and dialed in the
/// background; Settings is where one is entered or changed, at any point
/// after launch, never as a gate before it. See docs/APP_PLAN.md §9.
class DomoraMobileApp extends StatefulWidget {
  const DomoraMobileApp({super.key});

  @override
  State<DomoraMobileApp> createState() => _DomoraMobileAppState();
}

class _DomoraMobileAppState extends State<DomoraMobileApp> {
  final _store = DomoraStore();
  late final _client = HubClient(baseUrl: '', store: _store);

  @override
  void initState() {
    super.initState();
    HubClient.loadSavedAddress().then((saved) {
      if (saved != null && saved.isNotEmpty) _client.reconnectTo(saved);
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DOMORA',
      debugShowCheckedModeBanner: false,
      theme: domoraDarkTheme(),
      darkTheme: domoraDarkTheme(),
      themeMode: ThemeMode.dark,
      home: AppShell(store: _store, client: _client),
    );
  }
}
