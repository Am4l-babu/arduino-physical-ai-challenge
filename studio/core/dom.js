// Minimal hyperscript helper — no vdom, no diffing. Screens rebuild their
// own subtree on the data changes they care about; at DOMORA's data volume
// (a few hundred twin points, a handful of screens) that is simple and fast
// enough, and it keeps the whole app framework-free by design (see
// docs/APP_PLAN.md §2).

const SVG_TAGS = new Set([
  "svg", "g", "path", "circle", "rect", "text", "line", "polygon", "polyline", "defs",
  "linearGradient", "radialGradient", "stop", "clipPath", "use",
]);

export function h(tag, props = {}, children = []) {
  const svg = SVG_TAGS.has(tag);
  const el = svg
    ? document.createElementNS("http://www.w3.org/2000/svg", tag)
    : document.createElement(tag);

  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else if (svg) el.setAttribute(k, String(v));
    else if (k in el && typeof el[k] !== "function") el[k] = v;
    else el.setAttribute(k, String(v));
  }

  const kids = Array.isArray(children) ? children : [children];
  for (const child of kids) append(el, child);
  return el;
}

function append(el, child) {
  if (child == null || child === false) return;
  if (Array.isArray(child)) { for (const c of child) append(el, c); return; }
  el.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
}

// Replace a mount point's children with a freshly built node tree.
export function mount(target, node) {
  target.replaceChildren(node);
}

export function clear(target) {
  target.replaceChildren();
}

// Coalesce rapid store updates (a burst of twin points) into one render
// per animation frame, so a fast point stream never causes layout thrash.
export function raf(fn) {
  let scheduled = false;
  return (...args) => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; fn(...args); });
  };
}
