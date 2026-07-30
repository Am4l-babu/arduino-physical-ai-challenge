// Phase E — Settings: read-first, minimal. Port of studio/screens/settings.js.
// House and Nodes come from the real house knowledge graph (GET /graph, i.e.
// hub/config/house.json through hub.twin.graph.KnowledgeGraph). AI lists the
// intents hub/services/ai_query.py actually implements. Users is honest:
// this system has no accounts, roles, or login.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';
import '../widgets/incident_row.dart';

const _aiIntents = [
  'Power / energy — "why is power high?"',
  'Leak status — "is there a leak?"',
  'Appliance health — "which appliance is unhealthy?"',
  'Water usage (needs --journal) — "how much water was used?"',
  'What changed while away (needs --journal)',
  'House status overview',
];

class Asset {
  final String id;
  final String type;
  final String room;
  final List<String> commands;
  const Asset({required this.id, required this.type, required this.room, required this.commands});
}

List<Asset> parseAssets(Map<String, dynamic>? body) {
  final raw = (body?['assets'] as List?) ?? const [];
  return [
    for (final a in raw.cast<Map>())
      Asset(
        id: a['id'] as String,
        type: a['type'] as String? ?? '—',
        room: a['room'] as String? ?? '—',
        commands: ((a['commands'] as List?) ?? const []).cast<String>(),
      ),
  ];
}

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  List<Asset>? _assets;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final body = await HubScope.of(context).fetchGraph();
    if (!mounted) return;
    setState(() {
      _assets = body == null ? null : parseAssets(body);
      _loaded = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final assets = _assets;
    final rooms = assets == null ? <String>[] : (assets.map((a) => a.room).toSet().toList()..sort());
    final unavailable = _loaded ? 'House graph not available from this server.' : 'Loading…';

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(DomoraSpace.s4),
        children: [
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('House'),
                if (assets == null)
                  EmptyNote(unavailable)
                else
                  Wrap(
                    spacing: DomoraSpace.s2,
                    runSpacing: DomoraSpace.s2,
                    children: [for (final r in rooms) DomoraChip(r)],
                  ),
              ],
            ),
          ),
          const SizedBox(height: DomoraSpace.s4),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('Nodes / assets'),
                if (assets == null)
                  EmptyNote(unavailable)
                else
                  for (final a in assets) _AssetRow(asset: a),
              ],
            ),
          ),
          const SizedBox(height: DomoraSpace.s4),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const CardTitle('AI'),
                const Text(
                  'DOMORA AI answers are deterministic and grounded in the real twin / NILM ledger / journal — '
                  'no LLM in this build. What you can ask:',
                  style: TextStyle(fontSize: 12, color: DomoraColors.inkFaint, height: 1.4),
                ),
                const SizedBox(height: DomoraSpace.s2),
                for (final t in _aiIntents)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text('· $t', style: const TextStyle(fontSize: 13, color: DomoraColors.inkDim)),
                  ),
              ],
            ),
          ),
          const SizedBox(height: DomoraSpace.s4),
          const GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CardTitle('Users'),
                EmptyNote('Single-user. No accounts, roles, or login are implemented yet — anyone reaching this '
                    "server has full access. Don't expose it beyond a trusted network."),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AssetRow extends StatelessWidget {
  final Asset asset;
  const _AssetRow({required this.asset});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 3,
              child: Text(asset.id,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: DomoraColors.ink)),
            ),
            Expanded(
              flex: 2,
              child: Text(asset.type, style: const TextStyle(fontSize: 12, color: DomoraColors.inkDim)),
            ),
            Expanded(
              flex: 2,
              child: Text(asset.room, style: const TextStyle(fontSize: 12, color: DomoraColors.inkFaint)),
            ),
            Expanded(
              flex: 2,
              child: Text(asset.commands.isEmpty ? '—' : asset.commands.join(', '),
                  style: const TextStyle(fontSize: 11, color: DomoraColors.inkFaint)),
            ),
          ],
        ),
      );
}
