// Live transport: connects to the hub's /ws, feeds the store, reconnects on
// drop. Falls back to /playback.json for scrub-back if a recorded journal is
// being served (same contract the existing dashboard/ already proves out).
import { store } from "./store.js";

const RECONNECT_MS = 1500;

export function connectLive() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => store.setConnection("live");
  ws.onclose = () => { store.setConnection("down"); setTimeout(connectLive, RECONNECT_MS); };
  ws.onerror = () => ws.close();
  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.type === "snapshot") store.applySnapshot(msg);
    else if (msg.type === "point") store.applyPoint(msg);
    else if (msg.type === "event") store.applyEvent(msg);
  };
  return ws;
}

export async function tryPlayback() {
  try {
    const r = await fetch("/playback.json");
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export function boot() {
  tryPlayback().then((data) => {
    if (data) {
      store.setConnection("live");
      // Land on the resolved end-state; a playback screen can scrub earlier.
      for (const f of data.timeline || []) {
        if (f.type === "snapshot") store.applySnapshot(f);
        else if (f.type === "point") store.applyPoint(f);
        else if (f.type === "event") store.applyEvent(f);
      }
    } else {
      connectLive();
    }
  });
}
