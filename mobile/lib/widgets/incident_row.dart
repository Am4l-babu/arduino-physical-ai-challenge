// The cause → evidence → command → verify row. One widget, used by Water,
// Room, and History, because all three render the same ActionCard shape —
// the flagship "the house explains itself" surface. Port of the incidentRow
// helpers duplicated across studio/screens/{water,room,history}.js.
import 'package:flutter/material.dart';

import '../core/store.dart';
import '../theme/tokens.dart';
import 'health_dot.dart';

DomoraState actionState(String status) => switch (status) {
      'confirmed' => DomoraState.ok,
      'failed' => DomoraState.crit,
      _ => DomoraState.learn,
    };

String actionLabel(String status) => switch (status) {
      'confirmed' => 'verified',
      'failed' => 'escalated',
      _ => 'pending',
    };

class IncidentRow extends StatelessWidget {
  final ActionCard action;

  /// Head-only (dot + cause + status) is what Room and History show; the
  /// full row adds command/expectation/retries/reason, as Water does.
  final bool detailed;

  const IncidentRow({super.key, required this.action, this.detailed = true});

  @override
  Widget build(BuildContext context) {
    final state = actionState(action.status);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DomoraSpace.s2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: DomoraSpace.s2,
            runSpacing: 4,
            children: [
              HealthDot(state),
              Text(action.cause ?? 'action #${action.id}',
                  style: const TextStyle(fontWeight: FontWeight.w600, color: DomoraColors.ink, fontSize: 14)),
              DomoraChip(actionLabel(action.status), state: state),
            ],
          ),
          if (detailed) ...[
            const SizedBox(height: 4),
            _detail('command: ${action.command ?? '—'}'),
            _detail('expect: ${action.expect ?? '—'}'),
            if (action.retries > 0) _detail('retried ${action.retries}×'),
            if (action.reason != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(action.reason!,
                    style: const TextStyle(fontSize: 12, color: DomoraColors.stCrit)),
              ),
          ],
        ],
      ),
    );
  }

  Widget _detail(String text) => Text(
        text,
        style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkFaint),
      );
}

/// The section header every glass card uses ("Incidents", "Alerts", …).
class CardTitle extends StatelessWidget {
  final String text;
  const CardTitle(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: DomoraSpace.s2),
        child: Text(text,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
      );
}

/// The honest "there is no data for this" line — used wherever a screen would
/// otherwise be tempted to fabricate a widget. See docs/APP_PLAN.md §7.
class EmptyNote extends StatelessWidget {
  final String text;
  const EmptyNote(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Text(text,
      style: const TextStyle(color: DomoraColors.inkFaint, fontStyle: FontStyle.italic, fontSize: 13));
}
