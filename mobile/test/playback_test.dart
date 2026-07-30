// The scrub must be genuinely time-aware: reconstructing at t=0 has to show a
// house that hasn't detected anything yet, and reconstructing at the end has
// to show the real recorded incident. Replaying the whole timeline regardless
// of scrub position would look identical at every position and prove nothing.
// Fed the real playback.json captured from a `--playback` server built from an
// actual recorded `stuck`-scenario journal.
import 'package:domora_mobile/core/playback.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  final timeline = PlaybackTimeline.parse(loadJson('playback.json'))!;

  test('the real recorded journal parses into a non-trivial timeline', () {
    expect(timeline.isEmpty, isFalse);
    expect(timeline.tMax, 119, reason: 'the captured run is 120 ticks (0..119)');
  });

  test('t=0 has no dispatched action yet', () {
    final state = reconstructAt(timeline, 0);
    expect(state.actionOrder, isEmpty);
    expect(state.points, isNotEmpty, reason: 'points do exist at t=0 — only the incident has not happened');
  });

  test('the leak action appears only after its real dispatch tick (34)', () {
    expect(reconstructAt(timeline, 33).actionOrder, isEmpty);
    final after = reconstructAt(timeline, 34);
    expect(after.actionOrder, hasLength(1));
    expect(after.actions[after.actionOrder.first]!.cause, 'leak:main_line');
    expect(after.actions[after.actionOrder.first]!.command, 'domora/cmd/main_valve/close');
  });

  test('the action is still pending before escalation and failed after it (t=56)', () {
    final before = reconstructAt(timeline, 55);
    expect(before.actions[1]!.status, 'pending',
        reason: 'the stuck valve has not been given up on yet at t=55');

    final after = reconstructAt(timeline, 56);
    expect(after.actions[1]!.status, 'failed');
    expect(after.actions[1]!.reason, contains('actuation unverified'),
        reason: 'the real escalation reason from the journal, not a synthesized one');
  });

  test('end state carries the real twin points', () {
    final end = reconstructAt(timeline, timeline.tMax);
    expect(end.points['virtual.water.leak_suspected']!.value, true);
    expect(end.points['health.main_valve']!.value, 'suspect');
  });

  test('a missing journal (404) parses to null rather than an empty-looking run', () {
    expect(PlaybackTimeline.parse(null), isNull);
  });
}
