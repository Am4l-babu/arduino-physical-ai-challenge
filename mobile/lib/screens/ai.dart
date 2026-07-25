// Phase B — DOMORA AI: direct port of studio/screens/ai.js. Every answer
// comes from HubClient.askAi() -> POST /ai, which runs hub/services/
// ai_query.py against the real twin/NILM/journal — deterministic and
// offline, no LLM in this slice. See docs/APP_PLAN.md §4 Phase 2, §9.
import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../theme/tokens.dart';

const _quickPrompts = [
  "Why is today's power consumption high?",
  'Is there a leak?',
  'Which appliance is becoming unhealthy?',
  'What changed while I was away?',
  "What's the house's status?",
  'Run a simulation',
];

class ChatMessage {
  final String role; // user | assistant
  final String text;
  final Map<String, dynamic>? evidence;
  ChatMessage({required this.role, required this.text, this.evidence});
}

class AiScreen extends StatefulWidget {
  const AiScreen({super.key});

  @override
  State<AiScreen> createState() => _AiScreenState();
}

class _AiScreenState extends State<AiScreen> {
  final List<ChatMessage> messages = [];
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  bool _pending = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    final trimmed = text.trim();
    if (_pending || trimmed.isEmpty) return;
    setState(() {
      messages.add(ChatMessage(role: 'user', text: trimmed));
      _pending = true;
    });
    _controller.clear();
    _scrollToEnd();

    final client = HubScope.of(context);
    try {
      final data = await client.askAi(trimmed);
      final evidence = (data['evidence'] as Map?)?.cast<String, dynamic>();
      messages.add(ChatMessage(role: 'assistant', text: data['text'] as String? ?? '', evidence: evidence));
    } catch (_) {
      messages.add(ChatMessage(role: 'assistant', text: "Couldn't reach the hub — is it still running?"));
    }
    if (mounted) setState(() => _pending = false);
    _scrollToEnd();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: messages.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(DomoraSpace.s6),
                    child: Text(
                      'Ask DOMORA about the house — every answer is grounded in the real twin, not a guess.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: DomoraColors.inkFaint),
                    ),
                  ),
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(DomoraSpace.s4),
                  itemCount: messages.length,
                  itemBuilder: (context, i) => _Bubble(message: messages[i]),
                ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Wrap(
              spacing: DomoraSpace.s2,
              runSpacing: DomoraSpace.s2,
              children: [
                for (final p in _quickPrompts)
                  ActionChip(label: Text(p, style: const TextStyle(fontSize: 12)), onPressed: _pending ? null : () => _send(p)),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(DomoraSpace.s4),
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.mic_none_rounded, color: DomoraColors.inkFaint),
                onPressed: null,
                tooltip: "Voice mode isn't implemented yet — tracked in docs/APP_PLAN.md",
              ),
              Expanded(
                child: TextField(
                  controller: _controller,
                  style: const TextStyle(color: DomoraColors.ink),
                  decoration: const InputDecoration(hintText: 'Ask DOMORA…', border: OutlineInputBorder(), isDense: true),
                  onSubmitted: _send,
                ),
              ),
              const SizedBox(width: DomoraSpace.s2),
              FilledButton(
                onPressed: _pending ? null : () => _send(_controller.text),
                child: _pending
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Send'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  final ChatMessage message;
  const _Bubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        child: Column(
          crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Container(
              margin: const EdgeInsets.only(bottom: DomoraSpace.s2),
              padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s3, vertical: DomoraSpace.s2),
              decoration: BoxDecoration(
                color: isUser ? DomoraColors.accent : DomoraColors.bg2,
                borderRadius: BorderRadius.circular(DomoraRadius.r2),
                border: isUser ? null : Border.all(color: DomoraColors.line),
              ),
              child: Text(message.text, style: TextStyle(color: isUser ? DomoraColors.accentInk : DomoraColors.ink)),
            ),
            if (message.evidence != null && message.evidence!.isNotEmpty) _EvidenceCard(evidence: message.evidence!),
          ],
        ),
      ),
    );
  }
}

class _EvidenceCard extends StatelessWidget {
  final Map<String, dynamic> evidence;
  const _EvidenceCard({required this.evidence});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: DomoraSpace.s2),
      padding: const EdgeInsets.symmetric(horizontal: DomoraSpace.s3, vertical: DomoraSpace.s2),
      decoration: BoxDecoration(
        color: DomoraColors.bg1,
        borderRadius: BorderRadius.circular(DomoraRadius.r1),
        border: Border.all(color: DomoraColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [for (final e in evidence.entries) _evidenceRow(e.key, e.value)],
      ),
    );
  }

  Widget _evidenceRow(String k, dynamic v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 1),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(k, style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkFaint)),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                _fmtEvidenceValue(v),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkDim),
                textAlign: TextAlign.right,
              ),
            ),
          ],
        ),
      );
}

String _fmtEvidenceValue(dynamic v) {
  if (v == null) return '—';
  if (v is double) return v.toStringAsFixed(2);
  return v.toString();
}
