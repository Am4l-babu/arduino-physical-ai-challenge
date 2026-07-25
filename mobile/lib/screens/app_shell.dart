import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/hub_client.dart';
import '../core/store.dart';
import '../theme/tokens.dart';
import 'ai.dart';
import 'coming_soon.dart';
import 'home.dart';

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
      case 0:
        return const HomeScreen();
      case 1:
        return const AiScreen();
      case 2:
        return const ComingSoonScreen(title: 'Energy', note: 'Phase C — not built yet in the mobile app.');
      case 3:
        return const ComingSoonScreen(title: 'Water', note: 'Phase C — not built yet in the mobile app.');
      case 4:
        return const ComingSoonScreen(title: 'Security', note: 'Phase C — not built yet in the mobile app.');
      default:
        return const HomeScreen();
    }
  }

  @override
  Widget build(BuildContext context) {
    return StoreScope(
      store: widget.store,
      child: HubScope(
        client: widget.client,
        child: Scaffold(
          appBar: AppBar(
            title: const Text('DOMORA'),
            actions: [
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
