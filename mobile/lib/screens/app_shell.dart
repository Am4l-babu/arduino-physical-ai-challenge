import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/hub_client.dart';
import '../core/store.dart';
import '../theme/tokens.dart';
import 'ai.dart';
import 'energy.dart';
import 'history.dart';
import 'home.dart';
import 'insights.dart';
import 'room.dart';
import 'search.dart';
import 'security.dart';
import 'sensor.dart';
import 'settings.dart';
import 'water.dart';

class AppShell extends StatefulWidget {
  final DomoraStore store;
  final HubClient client;
  const AppShell({super.key, required this.store, required this.client});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _tab = 0;

  static const _tabs = [
    (icon: Icons.home_rounded, label: 'Home'),
    (icon: Icons.chat_bubble_rounded, label: 'AI'),
    (icon: Icons.bolt_rounded, label: 'Energy'),
    (icon: Icons.water_drop_rounded, label: 'Water'),
    (icon: Icons.shield_rounded, label: 'Security'),
  ];

  @override
  void dispose() {
    widget.client.dispose();
    super.dispose();
  }

  Widget _body() {
    switch (_tab) {
      case 1:
        return const AiScreen();
      case 2:
        return const EnergyScreen();
      case 3:
        return const WaterScreen();
      case 4:
        return const SecurityScreen();
      default:
        return const HomeScreen();
    }
  }

  /// Search is search-and-navigate only (see screens/search.dart) — the shell
  /// owns every destination it can reach, so the search box can never do
  /// anything the nav couldn't already do.
  Future<void> _openSearch(BuildContext context) async {
    final target = await pushScoped<SearchTarget>(context, const SearchScreen());
    if (target == null || !context.mounted) return;
    if (target.tab != null) {
      setState(() => _tab = target.tab!);
    } else if (target.roomId != null) {
      await pushScoped(context, RoomScreen(id: target.roomId!));
    } else if (target.pointKey != null) {
      await pushScoped(context, SensorScreen(pointKey: target.pointKey!));
    } else if (target.menu != null) {
      await _openMenu(context, target.menu!);
    }
  }

  Future<void> _openMenu(BuildContext context, String which) => switch (which) {
        'history' => pushScoped(context, const HistoryScreen()),
        'insights' => pushScoped(context, const InsightsScreen()),
        _ => pushScoped(context, const SettingsScreen()),
      };

  @override
  Widget build(BuildContext context) {
    return StoreScope(
      store: widget.store,
      child: HubScope(
        client: widget.client,
        child: Builder(
          builder: (innerContext) => Scaffold(
            appBar: AppBar(
              title: const Text('DOMORA'),
              actions: [
                IconButton(
                  icon: const Icon(Icons.search_rounded),
                  tooltip: 'Search screens, rooms, points',
                  onPressed: () => _openSearch(innerContext),
                ),
                PopupMenuButton<String>(
                  tooltip: 'More',
                  onSelected: (v) => _openMenu(innerContext, v),
                  itemBuilder: (context) => const [
                    PopupMenuItem(value: 'history', child: Text('History')),
                    PopupMenuItem(value: 'insights', child: Text('AI Insights')),
                    PopupMenuItem(value: 'settings', child: Text('Settings')),
                  ],
                ),
                AnimatedBuilder(
                  animation: widget.store,
                  builder: (context, _) => Padding(
                    padding: const EdgeInsets.only(right: DomoraSpace.s4),
                    child: _StatusPill(connection: widget.store.connection, now: widget.store.now),
                  ),
                ),
              ],
            ),
            body: _body(),
            bottomNavigationBar: BottomNavigationBar(
              currentIndex: _tab,
              onTap: (i) => setState(() => _tab = i),
              items: [for (final t in _tabs) BottomNavigationBarItem(icon: Icon(t.icon), label: t.label)],
            ),
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  final String connection;
  final int now;
  const _StatusPill({required this.connection, required this.now});

  @override
  Widget build(BuildContext context) {
    final color = switch (connection) {
      'live' => DomoraColors.stOk,
      'down' => DomoraColors.stCrit,
      _ => DomoraColors.inkFaint,
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(shape: BoxShape.circle, color: color)),
        const SizedBox(width: 6),
        Text(
          't=${now.toString().padLeft(3, '0')}',
          style: const TextStyle(fontSize: 12, color: DomoraColors.inkFaint, fontFamily: 'monospace'),
        ),
      ],
    );
  }
}
