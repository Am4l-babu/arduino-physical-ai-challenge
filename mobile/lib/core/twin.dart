// Derives the "living house" model from raw twin points — direct Dart port
// of studio/core/twin.js. Pure functions only; no widget code here. Every
// field traces to a real point key from the hub contract (docs/APP_PLAN.md
// §0); this file is the one place that mapping lives.
import '../theme/tokens.dart';
import 'store.dart';

dynamic _get(Map<String, Point> points, String key, [dynamic dflt]) => points[key]?.value ?? dflt;

double _asDouble(dynamic v, double dflt) {
  if (v is num) return v.toDouble();
  return dflt;
}

class WaterState {
  final double flowLpm;
  final double levelPct; // NaN if unknown
  final String valveState;
  final String pumpState;
  final double pumpCurrentA; // NaN if unknown
  final bool leak;
  final bool dryrun;
  final bool valveSuspect;
  final bool pumpSuspect;
  final DomoraState state;

  WaterState({
    required this.flowLpm,
    required this.levelPct,
    required this.valveState,
    required this.pumpState,
    required this.pumpCurrentA,
    required this.leak,
    required this.dryrun,
    required this.valveSuspect,
    required this.pumpSuspect,
    required this.state,
  });
}

WaterState deriveWater(Map<String, Point> points) {
  final flowLpm = _asDouble(_get(points, 'tank.line.flow_lpm', 0), 0);
  final levelPct = _asDouble(_get(points, 'water_tank.level_pct'), double.nan);
  final valveState = (_get(points, 'main_valve.valve_state', '—') as Object).toString();
  final pumpState = (_get(points, 'pump.pump_state', '—') as Object).toString();
  final pumpCurrentA = _asDouble(_get(points, 'pump.current_a'), double.nan);
  final leak = _get(points, 'virtual.water.leak_suspected', false) == true;
  final dryrun = _get(points, 'virtual.pump.dryrun_suspected', false) == true;
  final valveSuspect = _get(points, 'health.main_valve') == 'suspect';
  final pumpSuspect = _get(points, 'health.pump') == 'suspect';

  var state = DomoraState.ok;
  if (leak || valveSuspect || dryrun || pumpSuspect) {
    state = DomoraState.crit;
  } else if (!levelPct.isNaN && levelPct < 15) {
    state = DomoraState.warn;
  }

  return WaterState(
    flowLpm: flowLpm,
    levelPct: levelPct,
    valveState: valveState,
    pumpState: pumpState,
    pumpCurrentA: pumpCurrentA,
    leak: leak,
    dryrun: dryrun,
    valveSuspect: valveSuspect,
    pumpSuspect: pumpSuspect,
    state: state,
  );
}

class OccupancyState {
  final bool occupied;
  final bool pir;
  final bool radar;
  OccupancyState({required this.occupied, required this.pir, required this.radar});
}

OccupancyState deriveOccupancy(Map<String, Point> points) {
  return OccupancyState(
    occupied: _get(points, 'house.occupied', false) == true,
    pir: _get(points, 'living.pir', false) == true,
    radar: _get(points, 'living.radar', false) == true,
  );
}

double derivePowerW(Map<String, Point> points) => _asDouble(_get(points, 'main_panel.power_w'), double.nan);

class Zone {
  final String id;
  final String label;
  final DomoraState state;
  final String detail;
  Zone({required this.id, required this.label, required this.state, required this.detail});
}

List<Zone> deriveZones(Map<String, Point> points) {
  final water = deriveWater(points);
  final occ = deriveOccupancy(points);
  final power = derivePowerW(points);

  return [
    Zone(id: 'living', label: 'Living', state: DomoraState.ok, detail: occ.occupied ? 'occupied' : 'empty'),
    Zone(id: 'utility', label: 'Water / Utility', state: water.state, detail: _waterDetail(water)),
    Zone(
      id: 'panel',
      label: 'Main Panel',
      state: DomoraState.ok,
      detail: power.isNaN ? '—' : '${power.toStringAsFixed(0)} W',
    ),
  ];
}

String _waterDetail(WaterState w) {
  if (w.leak) return 'leak suspected';
  if (w.dryrun) return 'pump dry-run';
  if (w.valveSuspect) return 'valve suspect';
  return 'nominal';
}

DomoraState overallState(List<Zone> zones) {
  const order = [DomoraState.crit, DomoraState.warn, DomoraState.learn, DomoraState.pred, DomoraState.ok];
  for (final s in order) {
    if (zones.any((z) => z.state == s)) return s;
  }
  return DomoraState.ok;
}
