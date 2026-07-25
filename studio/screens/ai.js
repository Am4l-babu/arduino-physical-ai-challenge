// Phase 2 — DOMORA AI: a grounded chat screen. Every answer comes from
// POST /ai, which runs hub/services/ai_query.py against the real twin/NILM/
// journal — deterministic and offline, no LLM in this slice (see
// docs/APP_PLAN.md §4 Phase 2 and §7 for the honest scope of this).
import { h, mount } from "../core/dom.js";

const QUICK_PROMPTS = [
  "Why is today's power consumption high?",
  "Is there a leak?",
  "Which appliance is becoming unhealthy?",
  "What changed while I was away?",
  "What's the house's status?",
  "Run a simulation",
];

let messages = [];
let target = null;
let pending = false;

export function renderAI(mountTarget) {
  target = mountTarget;
  paint();
}

function paint() {
  mount(target, view());
  const log = target.querySelector("#ai-log");
  if (log) log.scrollTop = log.scrollHeight;
}

function view() {
  return h("div", { class: "ai-screen" }, [
    h("div", { class: "glass card ai-log", id: "ai-log" },
      messages.length
        ? messages.map(bubble)
        : h("div", { class: "empty" }, "Ask DOMORA about the house — every answer is grounded in the real twin, not a guess.")),
    h("div", { class: "ai-chips" }, QUICK_PROMPTS.map((p) =>
      h("button", { type: "button", class: "chip ai-chip", onclick: () => send(p) }, p))),
    h("form", { class: "ai-input-row", onsubmit: onSubmit }, [
      h("button", { type: "button", class: "mic-btn", disabled: true,
                    title: "Voice mode isn't implemented yet — tracked in docs/APP_PLAN.md" }, "\u{1F399}"),
      h("input", { id: "ai-input", type: "text", placeholder: "Ask DOMORA…", autocomplete: "off" }),
      h("button", { type: "submit", class: "send-btn" }, pending ? "…" : "Send"),
    ]),
  ]);
}

function onSubmit(e) {
  e.preventDefault();
  const input = target.querySelector("#ai-input");
  const text = input.value.trim();
  if (!text) return;
  send(text);
}

async function send(text) {
  if (pending) return;
  messages.push({ role: "user", text });
  pending = true;
  paint();
  const input = target.querySelector("#ai-input");
  if (input) input.value = "";
  try {
    const res = await fetch("/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    messages.push({ role: "assistant", text: data.text, evidence: data.evidence, intent: data.intent });
  } catch {
    messages.push({ role: "assistant", text: "Couldn't reach the hub — is it still running?", evidence: {} });
  }
  pending = false;
  paint();
}

function bubble(m) {
  return h("div", { class: `bubble ${m.role}` }, [
    h("div", { class: "bubble-text" }, m.text),
    m.evidence && Object.keys(m.evidence).length ? evidenceCard(m.evidence) : null,
  ]);
}

function evidenceCard(evidence) {
  return h("div", { class: "evidence" }, Object.entries(evidence).map(([k, v]) =>
    h("div", { class: "evidence-row" }, [
      h("span", { class: "k" }, k),
      h("span", { class: "v" }, fmtValue(v)),
    ])));
}

function fmtValue(v) {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}
