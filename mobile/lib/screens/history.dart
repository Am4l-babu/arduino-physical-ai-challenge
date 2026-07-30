// Phase E — History: scrub a recorded journal (GET /playback.json, present
// only when the hub was started with --playback demo.db). Port of
// studio/screens/history.js. Keeps its own reconstructed state rather than
// touching the live store, so scrubbing the past never corrupts what
// Home/Water/Energy show as "now" when the user switches tabs mid-scrub.
import 'dart:async';

import 'package:flutter/material.dart';

import '../core/app_scope.dart';
import '../core/format.dart';
import '../core/playback.dart';
import '../theme/tokens.dart';
import '../widgets/glass_card.dart';
import '../widgets/incident_row.dart';

const _playInterval = Duration(milliseconds: 200);

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  PlaybackTimeline? _timeline;
  bool _loaded = false;
  int _t = 0;
  bool _playing = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final timeline = PlaybackTimeline.parse(await HubScope.of(context).fetchPlayback());
    if (!mounted) return;
    setState(() {
      _timeline = timeline;
      _loaded = true;
      // Land on the resolved end-state; scrub back to watch it unfold.
      _t = timeline?.tMax ?? 0;
    });
  }

  void _stop() {
    _timer?.cancel();
    _timer = null;
    if (_playing) setState(() => _playing = false);
  }

  void _play() {
    final tMax = _timeline?.tMax ?? 0;
    if (_t >= tMax) setState(() => _t = 0);
    setState(() => _playing = true);
    _timer = Timer.periodic(_playInterval, (_) {
      if (_t >= tMax) {
        _stop();
        return;
      }
      setState(() => _t += 1);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('History')),
      body: _body(),
    );
  }

  Widget _body() {
    final timeline = _timeline;
    if (!_loaded) {
      return const Padding(
        padding: EdgeInsets.all(DomoraSpace.s4),
        child: GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [CardTitle('History'), EmptyNote('Loading recorded journal…')],
          ),
        ),
      );
    }
    if (timeline == null || timeline.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(DomoraSpace.s4),
        child: GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CardTitle('History'),
              EmptyNote('No recorded journal for this run. Home, Water, Energy, and Security already show what is '
                  'happening now. To browse history: run the hub with --journal demo.db, then serve it with '
                  '`python -m hub.services.api --playback demo.db`.'),
            ],
          ),
        ),
      );
    }

    final state = reconstructAt(timeline, _t);
    final keys = state.points.keys.toList()..sort();

    return ListView(
      padding: const EdgeInsets.all(DomoraSpace.s4),
      children: [
        GlassCard(
          child: Row(
            children: [
              IconButton(
                icon: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded),
                color: DomoraColors.accent,
                onPressed: () => _playing ? _stop() : _play(),
                tooltip: _playing ? 'Pause' : 'Play',
              ),
              Expanded(
                child: Slider(
                  value: _t.toDouble().clamp(0, timeline.tMax.toDouble()),
                  min: 0,
                  max: timeline.tMax.toDouble(),
                  onChanged: (v) {
                    _stop();
                    setState(() => _t = v.round());
                  },
                ),
              ),
              Text('${fmtTick(_t)} / ${fmtTick(timeline.tMax)}',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkFaint)),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Actions at this point'),
              if (state.actionOrder.isEmpty)
                const EmptyNote('No action dispatched yet at this tick.')
              else
                for (final id in state.actionOrder)
                  IncidentRow(action: state.actions[id]!, detailed: false),
            ],
          ),
        ),
        const SizedBox(height: DomoraSpace.s4),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardTitle('Points at this point'),
              for (final k in keys)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  // Some twin points carry evidence maps, whose string form is
                  // far wider than a phone — both columns are bounded and
                  // ellipsized so a long value can't blow up the row.
                  child: Row(
                    children: [
                      Expanded(
                        flex: 3,
                        child: Text(k,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.inkDim)),
                      ),
                      const SizedBox(width: DomoraSpace.s2),
                      Expanded(
                        flex: 2,
                        child: Text(fmtValue(state.points[k]!.value),
                            overflow: TextOverflow.ellipsis,
                            textAlign: TextAlign.right,
                            style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: DomoraColors.ink)),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
