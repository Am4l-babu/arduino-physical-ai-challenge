// The NILM appliance ledger, straight from GET /nilm (hub/agents/energy.py's
// own report()) — see core/twin.js for why this isn't reconstructed from
// twin points client-side.
export async function fetchNilm() {
  try {
    const res = await fetch("/nilm");
    if (!res.ok) return null;
    const body = await res.json();
    const byName = body.energy_wh || {};
    return Object.entries(byName)
      .map(([name, energyWh]) => ({ name, energyWh }))
      .sort((a, b) => b.energyWh - a.energyWh);
  } catch {
    return null;
  }
}
