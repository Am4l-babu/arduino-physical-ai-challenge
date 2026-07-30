// Journal playback — rebuilds the recorded run's state *at a given tick*.
// Port of the reconstructAt() logic in studio/screens/history.js, lifted into
// core/ so it can be unit-tested against a real recorded journal rather than
// only through a widget.
//
// Time-aware on purpose: scrubbing to t=0 must show a house that hasn't
// detected anything yet, and scrubbing to the end must show the real
// incident. Replaying the whole timeline regardless of the scrub position
// would look identical at every position and prove nothing.
import 'store.dart';

class PlaybackTimeline {
  final List<Map<String, dynamic>> frames; // sorted by t, as JournalReader emits
  final int tMax;
  const PlaybackTimeline({required this.frames, required this.tMax});

  bool get isEmpty => frames.isEmpty;

  /// Parses a real GET /playback.json body. Returns null when the server has
  /// no journal (it 404s unless started with --playback).
  static PlaybackTimeline? parse(Map<String, dynamic>? body) {
    if (body == null) return null;
    final raw = (body['timeline'] as List?) ?? const [];
    return PlaybackTimeline(
      frames: raw.map((f) => (f as Map).cast<String, dynamic>()).toList(),
      tMax: (body['t_max'] as num?)?.toInt() ?? 0,
    );
  }
}

class PlaybackState {
  final Map<String, Point> points;
  final Map<int, ActionCard> actions;
  final List<int> actionOrder; // most-recent-first, same as the live store
  const PlaybackState({required this.points, required this.actions, required this.actionOrder});
}

PlaybackState reconstructAt(PlaybackTimeline timeline, int tick) {
  final points = <String, Point>{};
  final actions = <int, ActionCard>{};
  final actionOrder = <int>[];

  for (final f in timeline.frames) {
    final t = (f['t'] as num).toInt();
    if (t > tick) break; // JournalReader.timeline() is sorted by t
    if (f['type'] == 'point') {
      points[f['key'] as String] = Point(
        value: f['value'],
        t: t,
        source: f['source'] as String?,
        confidence: (f['confidence'] as num?)?.toDouble(),
      );
    } else if (f['type'] == 'event') {
      final topic = f['topic'] as String;
      final payload = (f['payload'] as Map?)?.cast<String, dynamic>() ?? const {};
      final a = payload['action'];
      if ((topic == 'domora/plan/action' || topic == 'domora/act/dispatched') && a != null) {
        final action = (a as Map).cast<String, dynamic>();
        final id = (action['id'] as num).toInt();
        final card = actions.putIfAbsent(id, () {
          actionOrder.insert(0, id);
          return ActionCard(id);
        });
        card.cause = action['cause'] as String? ?? card.cause;
        card.command = action['command_topic'] as String? ?? card.command;
        if (action['evidence'] != null) {
          card.evidence = (action['evidence'] as Map).cast<String, dynamic>();
        }
        if (action['expectation'] != null) {
          card.expect = (action['expectation'] as Map)['describe'] as String?;
        }
        // The journal stores each action's *final* status on every frame that
        // carries it; the timeline's own verify/alert frames are what make the
        // scrub time-aware, so the embedded status is deliberately ignored.
      } else if (topic == 'domora/verify/confirmed') {
        final id = (payload['action_id'] as num?)?.toInt();
        if (id != null && actions.containsKey(id)) actions[id]!.status = 'confirmed';
      } else if (topic.startsWith('domora/alert')) {
        final id = (payload['action_id'] as num?)?.toInt();
        if (id != null && actions.containsKey(id)) {
          actions[id]!.status = 'failed';
          actions[id]!.reason = payload['reason'] as String?;
        }
      }
    }
  }

  return PlaybackState(points: points, actions: actions, actionOrder: actionOrder);
}
