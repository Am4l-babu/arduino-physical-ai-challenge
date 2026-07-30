// Minimal InheritedWidget plumbing — deliberately no state-management
// package (see docs/APP_PLAN.md §9: ChangeNotifier + Flutter SDK only).
import 'package:flutter/material.dart';
import 'hub_client.dart';
import 'store.dart';

class StoreScope extends InheritedNotifier<DomoraStore> {
  const StoreScope({super.key, required DomoraStore store, required super.child}) : super(notifier: store);

  static DomoraStore of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<StoreScope>()!.notifier!;
}

class HubScope extends InheritedWidget {
  final HubClient client;
  const HubScope({super.key, required this.client, required super.child});

  static HubClient of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<HubScope>()!.client;

  @override
  bool updateShouldNotify(HubScope oldWidget) => oldWidget.client != client;
}

/// Pushes a detail page with the store/hub scopes re-applied.
///
/// A pushed route is a sibling of the route AppShell lives in, not a
/// descendant of it, so it would not otherwise inherit StoreScope/HubScope.
/// Rather than hoist the scopes above MaterialApp (which would build them
/// before the user has picked a hub on the Connect screen), the detail routes
/// re-wrap the same instances — one store, one client, still shared.
Future<T?> pushScoped<T>(BuildContext context, Widget page) {
  final store = StoreScope.of(context);
  final client = HubScope.of(context);
  return Navigator.of(context).push<T>(
    MaterialPageRoute(builder: (_) => StoreScope(store: store, child: HubScope(client: client, child: page))),
  );
}
