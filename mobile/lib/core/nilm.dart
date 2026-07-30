// The NILM appliance ledger, straight from GET /nilm (hub/agents/energy.py's
// own report()) — port of studio/core/nilm.js. Deliberately NOT reconstructed
// client-side from `nilm.*` twin points: label_nearest() renames a cluster by
// copying its points to the new name and (correctly, per hub/twin/state.py's
// "points are never deleted" design) never retires the old ones, so a
// relabelled appliance shows up twice. See studio/core/twin.js's long note.

class NilmEntry {
  final String name;
  final double energyWh;
  const NilmEntry(this.name, this.energyWh);
}

class NilmCluster {
  final String label;
  final double meanW;
  final int events;
  const NilmCluster({required this.label, required this.meanW, required this.events});
}

class NilmReport {
  final List<NilmCluster> clusters;
  final Map<String, double> energyWh;
  const NilmReport({required this.clusters, required this.energyWh});

  /// Ledger entries, largest consumer first — the order the bar chart wants.
  List<NilmEntry> get ledger {
    final entries = energyWh.entries.map((e) => NilmEntry(e.key, e.value)).toList();
    entries.sort((a, b) => b.energyWh.compareTo(a.energyWh));
    return entries;
  }

  NilmCluster? clusterFor(String name) {
    for (final c in clusters) {
      if (c.label == name) return c;
    }
    return null;
  }
}

/// Parses a real GET /nilm body. Returns null for a missing/unusable body so
/// screens can say "no NILM data" honestly instead of showing zeros.
NilmReport? parseNilm(Map<String, dynamic>? body) {
  if (body == null) return null;
  final rawClusters = (body['clusters'] as List?) ?? const [];
  final rawEnergy = (body['energy_wh'] as Map?)?.cast<String, dynamic>() ?? const {};
  return NilmReport(
    clusters: [
      for (final c in rawClusters.cast<Map>())
        NilmCluster(
          label: c['label'] as String,
          meanW: (c['mean_w'] as num).toDouble(),
          events: (c['events'] as num).toInt(),
        ),
    ],
    energyWh: {for (final e in rawEnergy.entries) e.key: (e.value as num).toDouble()},
  );
}
