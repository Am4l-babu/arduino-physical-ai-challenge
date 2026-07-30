// Phase E — AI Insights: prioritized observation cards from core/insights.dart.
// Port of studio/screens/insights.js. Nothing here computes anything new —
// every card is a different presentation of a signal already shown elsewhere.
import 'dart:async';

import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/insights.dart';
import '../core/nilm.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/health_dot.dart';

class InsightsScreen extends StatefulWidget {
  const InsightsScreen({super.key});

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> {
  List<NilmEntry> _nilm = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final report = parseNilm(await HubScope.of(context).fetchNilm());
    if (mounted && report != null) setState(() => _nilm = report.ledger);
  }

  @override
  Widget build(BuildContext context) {
    final store = StoreScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('AI Insights')),
      body: AnimatedBuilder(
        animation: store,
        builder: (context, _) {
          final cards = deriveInsights(store, _nilm);
          return ListView(
            padding: const EdgeInsets.all(DomoraSpace.s4),
            children: [
              for (final c in cards) ...[
                _InsightCard(insight: c),
                const SizedBox(height: DomoraSpace.s3),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _InsightCard extends StatelessWidget {
  final Insight insight;
  const _InsightCard({required this.insight});

  static DomoraState _stateFor(InsightPriority p) => switch (p) {
        InsightPriority.critical => DomoraState.crit,
        InsightPriority.warning => DomoraState.warn,
        InsightPriority.info => DomoraState.learn,
      };

  @override
  Widget build(BuildContext context) {
    final state = _stateFor(insight.priority);
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              HealthDot(state),
              const SizedBox(width: DomoraSpace.s2),
              DomoraChip(insight.priority.name, state: state),
            ],
          ),
          const SizedBox(height: DomoraSpace.s2),
          Text(insight.text, style: const TextStyle(fontSize: 14, color: DomoraColors.ink, height: 1.35)),
          if (insight.evidence.isNotEmpty) ...[
            const SizedBox(height: DomoraSpace.s2),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s3, vertical: DomoraSpace.s2),
              decoration: BoxDecoration(
                color: DomoraColors.bg1,
                borderRadius: BorderRadius.circular(DomoraRadius.r1),
                border: Border.all(color: DomoraColors.line),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final e in insight.evidence.entries)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 1),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(e.key,
                              style: const TextStyle(
                                  fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkFaint)),
                          const SizedBox(width: DomoraSpace.s2),
                          Flexible(
                            child: Text('${e.value}',
                                textAlign: TextAlign.right,
                                style: const TextStyle(
                                    fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkDim)),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
