// The live twin state model — direct Dart port of studio/core/store.js.
// One store, filled by hub_client.dart's WebSocket handler, read by every
// screen via ChangeNotifier. Shaped around the three message types the hub
// actually emits (snapshot / point / event) — see docs/APP_PLAN.md §0.
import 'package:flutter/foundation.dart';

class Point {
  final dynamic value;
  final int t;
  final String? source;
  final double? confidence;
  const Point({required this.value, required this.t, this.source, this.confidence});
}

class SeriesPoint {
  final int t;
  final double value;
  const SeriesPoint(this.t, this.value);
}

class FeedEntry {
  final String topic;
  final Map<String, dynamic> payload;
  final int t;
  const FeedEntry({required this.topic, required this.payload, required this.t});
}

class ActionCard {
  final int id;
  String? cause;
  String? command;
  Map<String, dynamic>? evidence;
  String? expect;
  int retries = 0;
  String status = 'pending'; // pending | confirmed | failed
  String? reason;
  ActionCard(this.id);
}

class DomoraStore extends ChangeNotifier {
  static const _seriesLimit = 300; // per key — this session only, see APP_PLAN §7
  static const _feedLimit = 80;

  // unconfigured: no hub address set yet (or none reachable to attempt) —
  // the honest default before HubClient.connect() has ever been asked to
  // dial anything. connecting/live/down all imply an attempt is underway.
  String connection = 'unconfigured'; // unconfigured | connecting | live | down
  int now = 0;
  final Map<String, Point> points = {};
  final Map<String, List<SeriesPoint>> series = {};
  final Map<int, ActionCard> actions = {};
  final List<int> actionOrder = []; // most-recent-first
  final List<FeedEntry> feed = []; // most-recent-first

  void setConnection(String status) {
    connection = status;
    notifyListeners();
  }

  void applySnapshot(Map<String, dynamic> msg) {
    now = _asInt(msg['t']) ?? 0;
    points.clear();
    final pts = (msg['points'] as Map?)?.cast<String, dynamic>() ?? const {};
    pts.forEach((key, v) {
      final map = (v as Map).cast<String, dynamic>();
      final p = Point(
        value: map['value'],
        t: _asInt(map['t']) ?? now,
        source: map['source'] as String?,
        confidence: (map['confidence'] as num?)?.toDouble(),
      );
      points[key] = p;
      _pushSeries(key, p.t, p.value);
    });
    notifyListeners();
  }

  void applyPoint(Map<String, dynamic> msg) {
    now = _asInt(msg['t']) ?? now;
    final key = msg['key'] as String;
    final p = Point(
      value: msg['value'],
      t: now,
      source: msg['source'] as String?,
      confidence: (msg['confidence'] as num?)?.toDouble(),
    );
    points[key] = p;
    _pushSeries(key, p.t, p.value);
    notifyListeners();
  }

  void applyEvent(Map<String, dynamic> msg) {
    now = _asInt(msg['t']) ?? now;
    final topic = msg['topic'] as String;
    final payload = (msg['payload'] as Map?)?.cast<String, dynamic>() ?? const {};
    feed.insert(0, FeedEntry(topic: topic, payload: payload, t: now));
    if (feed.length > _feedLimit) feed.removeLast();

    final a = payload['action'];
    if ((topic == 'domora/plan/action' || topic == 'domora/act/dispatched') && a != null) {
      _upsertAction((a as Map).cast<String, dynamic>());
    } else if (topic == 'domora/verify/confirmed') {
      final id = _asInt(payload['action_id']);
      if (id != null) _markAction(id, 'confirmed');
    } else if (topic.startsWith('domora/alert')) {
      final id = _asInt(payload['action_id']);
      if (id != null) _markAction(id, 'failed', reason: payload['reason'] as String?);
    }
    notifyListeners();
  }

  void _pushSeries(String key, int t, dynamic value) {
    if (value is! num) return;
    final arr = series.putIfAbsent(key, () => []);
    if (arr.isNotEmpty && arr.last.t == t) {
      arr[arr.length - 1] = SeriesPoint(t, value.toDouble());
      return;
    }
    arr.add(SeriesPoint(t, value.toDouble()));
    if (arr.length > _seriesLimit) arr.removeAt(0);
  }

  List<SeriesPoint> seriesFor(String key) => series[key] ?? const [];

  void _upsertAction(Map<String, dynamic> a) {
    final id = _asInt(a['id'])!;
    final m = actions.putIfAbsent(id, () {
      actionOrder.insert(0, id);
      return ActionCard(id);
    });
    m.cause = a['cause'] as String? ?? m.cause;
    m.command = a['command_topic'] as String? ?? m.command;
    if (a['evidence'] != null) m.evidence = (a['evidence'] as Map).cast<String, dynamic>();
    final expectation = a['expectation'];
    if (expectation != null) m.expect = (expectation as Map)['describe'] as String?;
    if (a['retries'] != null) m.retries = _asInt(a['retries'])!;
  }

  void _markAction(int id, String status, {String? reason}) {
    final m = actions.putIfAbsent(id, () {
      actionOrder.insert(0, id);
      return ActionCard(id);
    });
    m.status = status;
    if (reason != null) m.reason = reason;
  }

  dynamic point(String key, [dynamic dflt]) => points[key]?.value ?? dflt;

  void reset() {
    now = 0;
    points.clear();
    series.clear();
    actions.clear();
    actionOrder.clear();
    feed.clear();
    notifyListeners();
  }

  static int? _asInt(dynamic v) => v == null ? null : (v as num).toInt();
}
