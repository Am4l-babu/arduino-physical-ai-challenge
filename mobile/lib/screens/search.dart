// Phase E — Search: the mobile equivalent of Studio's ⌘K command bar.
// Searches screens, rooms, and live twin points, then navigates.
//
// Deliberately search-and-navigate only — it does NOT issue commands. This
// system's only actuation path is the planner dispatching through
// hub/agents/safety.py's capability table, and CLAUDE.md requires an explicit
// invariant review before that table changes. A search box on a phone doesn't
// get to add actuation as a side effect any more than the web command bar
// did. See docs/APP_PLAN.md §7, §9.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/store.dart';
import '../theme/tokens.dart';

/// What a chosen result means to the shell: switch to a bottom-nav tab, or
/// push a detail page. The shell owns navigation; this screen only picks.
class SearchTarget {
  final String label;
  final String hint;
  final int? tab; // index into AppShell's bottom nav
  final String? roomId;
  final String? pointKey;
  final String? menu; // 'history' | 'insights' | 'settings'

  const SearchTarget({
    required this.label,
    required this.hint,
    this.tab,
    this.roomId,
    this.pointKey,
    this.menu,
  });
}

const searchScreens = [
  SearchTarget(label: 'Home', hint: 'screen', tab: 0),
  SearchTarget(label: 'DOMORA AI', hint: 'screen', tab: 1),
  SearchTarget(label: 'Energy', hint: 'screen', tab: 2),
  SearchTarget(label: 'Water', hint: 'screen', tab: 3),
  SearchTarget(label: 'Security', hint: 'screen', tab: 4),
  SearchTarget(label: 'History', hint: 'screen', menu: 'history'),
  SearchTarget(label: 'AI Insights', hint: 'screen', menu: 'insights'),
  SearchTarget(label: 'Settings', hint: 'screen', menu: 'settings'),
];

const searchRooms = [
  SearchTarget(label: 'Room: Living', hint: 'room', roomId: 'living'),
  SearchTarget(label: 'Room: Water / Utility', hint: 'room', roomId: 'utility'),
  SearchTarget(label: 'Room: Main Panel', hint: 'room', roomId: 'panel'),
];

/// Points only appear once the user types — the full point list is long, and
/// showing all of it before a query would bury the screens and rooms.
List<SearchTarget> searchResults(String query, Iterable<String> pointKeys) {
  final q = query.trim().toLowerCase();
  final screens = searchScreens.where((s) => q.isEmpty || s.label.toLowerCase().contains(q));
  final rooms = searchRooms.where((r) => q.isEmpty || r.label.toLowerCase().contains(q));
  final points = q.isEmpty
      ? const <SearchTarget>[]
      : pointKeys
          .where((k) => k.toLowerCase().contains(q))
          .take(8)
          .map((k) => SearchTarget(label: k, hint: 'point', pointKey: k));
  return [...screens, ...rooms, ...points].take(12).toList();
}

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) => _build(context, store),
    );
  }

  Widget _build(BuildContext context, DomoraStore store) {
    final results = searchResults(_query, store.points.keys);
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _controller,
          autofocus: true,
          style: const TextStyle(color: DomoraColors.ink, fontSize: 16),
          decoration: const InputDecoration(
            hintText: 'Search screens, rooms, points…',
            border: InputBorder.none,
          ),
          onChanged: (v) => setState(() => _query = v),
        ),
      ),
      body: results.isEmpty
          ? const Padding(
              padding: EdgeInsets.all(DomoraSpace.s6),
              child: Text('No matches.', style: TextStyle(color: DomoraColors.inkFaint)),
            )
          : ListView(
              children: [
                for (final r in results)
                  ListTile(
                    dense: true,
                    leading: SizedBox(
                      width: 52,
                      child: Text(r.hint,
                          style: const TextStyle(fontSize: 10, letterSpacing: 0.4, color: DomoraColors.inkFaint)),
                    ),
                    title: Text(r.label,
                        style: TextStyle(
                          fontSize: 14,
                          color: DomoraColors.ink,
                          fontFamily: r.hint == 'point' ? 'monospace' : null,
                        )),
                    onTap: () => Navigator.of(context).pop(r),
                  ),
              ],
            ),
    );
  }
}
