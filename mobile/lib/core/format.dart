// Formatting helpers shared by every screen — direct Dart port of
// studio/core/format.js. No locale/timezone guessing: the hub speaks in sim
// ticks (t) today; wall-clock formatting is added when a real node stream
// carries wall-clock timestamps.

String fmtNum(double? v, [int digits = 1]) {
  if (v == null || v.isNaN) return '—';
  return v.toStringAsFixed(digits);
}

String fmtPct(double? v, [int digits = 0]) {
  if (v == null || v.isNaN) return '—';
  return '${v.toStringAsFixed(digits)}%';
}

String fmtTick(int? t) => 't=${(t ?? 0).toString().padLeft(3, '0')}';

String fmtWatts(double? v) {
  if (v == null || v.isNaN) return '—';
  return v >= 1000 ? '${(v / 1000).toStringAsFixed(2)} kW' : '${v.toStringAsFixed(0)} W';
}

/// Renders any twin point value — the twin carries bools, numbers, strings
/// and evidence maps through the same {value,t,source,confidence} shape.
String fmtValue(dynamic v) {
  if (v == null) return '—';
  if (v is bool) return v ? 'true' : 'false';
  if (v is num) {
    if (v is int || v == v.roundToDouble()) return v.toInt().toString();
    return v.toStringAsFixed(2);
  }
  if (v is Map || v is List) return v.toString();
  return v.toString();
}
