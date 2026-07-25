// Minimal InheritedWidget plumbing — deliberately no state-management
// package (see docs/APP_PLAN.md §9: ChangeNotifier + Flutter SDK only).
import 'package:flutter/widgets.dart';
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
