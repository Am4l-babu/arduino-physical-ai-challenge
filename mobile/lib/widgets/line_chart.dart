// Single-series trend chart — CustomPainter port of studio/ui/line-chart.js,
// same mark specs (line + 10%-opacity area, hairline grid at 0/50/100%, end
// dot + end label, crosshair readout). Sequential color job, one hue, per
// .claude/skills/dataviz; the palette was validated once during the Studio
// build and is ported here as Dart constants rather than re-derived.
//
// Difference from the web version, on purpose: there is no hover on a phone.
// The crosshair is driven by touch (tap or drag along the plot) and clears on
// release, which is the same affordance a mouse hover gives — a value readout
// on demand — through the input the device actually has.
import 'package:flutter/material.dart';

import '../core/store.dart';
import '../theme/tokens.dart';

const _pad = EdgeInsets.only(top: 10, right: 12, bottom: 20, left: 44);

class DomoraLineChart extends StatefulWidget {
  final List<SeriesPoint> data;
  final double height;
  final Color? color;
  final String unit;
  final String Function(double)? valueFmt;

  const DomoraLineChart({
    super.key,
    required this.data,
    this.height = 160,
    this.color,
    this.unit = '',
    this.valueFmt,
  });

  @override
  State<DomoraLineChart> createState() => _DomoraLineChartState();
}

class _DomoraLineChartState extends State<DomoraLineChart> {
  int? _hoverIndex;

  void _updateHover(Offset local, double width) {
    final plotW = width - _pad.left - _pad.right;
    if (plotW <= 0 || widget.data.length < 2) return;
    final frac = ((local.dx - _pad.left) / plotW).clamp(0.0, 1.0);
    final idx = (frac * (widget.data.length - 1)).round();
    if (idx != _hoverIndex) setState(() => _hoverIndex = idx);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.data.length < 2) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: DomoraSpace.s4),
        child: Text(
          'Not enough data yet — the trend needs a few more ticks.',
          style: TextStyle(color: DomoraColors.inkFaint, fontStyle: FontStyle.italic, fontSize: 13),
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapDown: (d) => _updateHover(d.localPosition, width),
          onTapUp: (_) => setState(() => _hoverIndex = null),
          onTapCancel: () => setState(() => _hoverIndex = null),
          onHorizontalDragUpdate: (d) => _updateHover(d.localPosition, width),
          onHorizontalDragEnd: (_) => setState(() => _hoverIndex = null),
          child: SizedBox(
            width: width,
            height: widget.height,
            child: CustomPaint(
              painter: _LinePainter(
                data: widget.data,
                color: widget.color ?? DomoraColors.accent,
                unit: widget.unit,
                fmt: widget.valueFmt ?? ((v) => v.toStringAsFixed(1)),
                hoverIndex: _hoverIndex,
              ),
            ),
          ),
        );
      },
    );
  }
}

class _LinePainter extends CustomPainter {
  final List<SeriesPoint> data;
  final Color color;
  final String unit;
  final String Function(double) fmt;
  final int? hoverIndex;

  _LinePainter({
    required this.data,
    required this.color,
    required this.unit,
    required this.fmt,
    required this.hoverIndex,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width - _pad.left - _pad.right;
    final plotH = size.height - _pad.top - _pad.bottom;
    if (w <= 0 || plotH <= 0) return;

    final ts = data.map((d) => d.t).toList();
    final vs = data.map((d) => d.value).toList();
    final tMin = ts.reduce((a, b) => a < b ? a : b).toDouble();
    final tMax = ts.reduce((a, b) => a > b ? a : b).toDouble();
    final vMin = vs.fold<double>(0, (a, b) => a < b ? a : b);
    final vMax = vs.fold<double>(vMin + 1, (a, b) => a > b ? a : b) * 1.08;
    final vSpan = (vMax - vMin) == 0 ? 1.0 : (vMax - vMin);

    double x(int t) => _pad.left + (tMax == tMin ? 0 : ((t - tMin) / (tMax - tMin)) * w);
    double y(double v) => _pad.top + plotH - ((v - vMin) / vSpan) * plotH;

    // hairline grid + axis labels (0 / 50 / 100 % of range)
    final gridPaint = Paint()
      ..color = DomoraColors.line
      ..strokeWidth = 1;
    for (final f in const [0.0, 0.5, 1.0]) {
      final gy = _pad.top + plotH * f;
      canvas.drawLine(Offset(_pad.left, gy), Offset(size.width - _pad.right, gy), gridPaint);
      _text(canvas, fmt(vMax - (vMax - vMin) * f),
          Offset(_pad.left - 6, gy), rightAligned: true, centerY: true,
          color: DomoraColors.inkFaint, fontSize: 10);
    }

    final path = Path();
    for (var i = 0; i < data.length; i++) {
      final px = x(data[i].t), py = y(data[i].value);
      if (i == 0) {
        path.moveTo(px, py);
      } else {
        path.lineTo(px, py);
      }
    }

    final area = Path.from(path)
      ..lineTo(x(data.last.t), _pad.top + plotH)
      ..lineTo(x(data.first.t), _pad.top + plotH)
      ..close();
    canvas.drawPath(area, Paint()..color = color.withValues(alpha: 0.10));
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeJoin = StrokeJoin.round,
    );

    // end dot + direct end label (identity without a legend)
    final last = data.last;
    canvas.drawCircle(Offset(x(last.t), y(last.value)), 4, Paint()..color = color);
    _text(
      canvas,
      '${fmt(last.value)}$unit',
      Offset((x(last.t) + 6).clamp(_pad.left, size.width - _pad.right - 4),
          (y(last.value) - 18).clamp(_pad.top, _pad.top + plotH)),
      color: DomoraColors.ink,
      fontSize: 11,
      bold: true,
    );

    // touch crosshair + readout
    final hi = hoverIndex;
    if (hi != null && hi >= 0 && hi < data.length) {
      final d = data[hi];
      final cx = x(d.t), cy = y(d.value);
      canvas.drawLine(
        Offset(cx, _pad.top),
        Offset(cx, _pad.top + plotH),
        Paint()
          ..color = DomoraColors.lineStrong
          ..strokeWidth = 1,
      );
      canvas.drawCircle(Offset(cx, cy), 4, Paint()..color = color);
      final label = '${fmtTickShort(d.t)}  ${fmt(d.value)}$unit';
      final tx = (cx + 8).clamp(_pad.left, size.width - _pad.right - 90);
      final ty = (cy - 34).clamp(_pad.top, _pad.top + plotH - 20);
      canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromLTWH(tx - 4, ty - 2, 92, 20), const Radius.circular(4)),
        Paint()..color = DomoraColors.bg1.withValues(alpha: 0.92),
      );
      _text(canvas, label, Offset(tx, ty), color: DomoraColors.ink, fontSize: 11, mono: true);
    }
  }

  static String fmtTickShort(int t) => 't=$t';

  /// `at` is the top-left of the text unless overridden: `rightAligned` puts
  /// its right edge at `at.dx`, `centerY` centers it on `at.dy`.
  void _text(
    Canvas canvas,
    String s,
    Offset at, {
    bool rightAligned = false,
    bool centerY = false,
    required Color color,
    required double fontSize,
    bool bold = false,
    bool mono = false,
  }) {
    final tp = TextPainter(
      text: TextSpan(
        text: s,
        style: TextStyle(
          color: color,
          fontSize: fontSize,
          fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
          fontFamily: mono ? 'monospace' : null,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final dx = rightAligned ? at.dx - tp.width : at.dx;
    final dy = centerY ? at.dy - tp.height / 2 : at.dy;
    tp.paint(canvas, Offset(dx, dy));
  }

  @override
  bool shouldRepaint(_LinePainter old) =>
      old.data != data || old.hoverIndex != hoverIndex || old.color != color;
}
