// Journal-backed history for a point key, with an honest fallback. Only
// --playback runs have a journal (hub/services/api.py's /history 404s
// otherwise) — screens call this once per key and fall back to the live
// session buffer (store.series) rather than pretending multi-day history
// exists. See docs/APP_PLAN.md §7.
export async function fetchHistory(key, limit = 500) {
  try {
    const res = await fetch(`/history?key=${encodeURIComponent(key)}&limit=${limit}`);
    if (!res.ok) return null;
    const body = await res.json();
    return (body.points || []).map(([t, value]) => ({ t, value }));
  } catch {
    return null;
  }
}
