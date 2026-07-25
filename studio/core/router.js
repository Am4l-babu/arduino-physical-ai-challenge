// Hash router: instant, offline, no server-side routing required.
// Supports simple :param segments (e.g. "/room/:id") — first-match-wins,
// so register more specific patterns before broader fallbacks.
const routes = []; // [{ regex, keys, render }]
let fallback = null;
let mountTarget = null;
let onNavigate = null;

export function register(pathPattern, renderFn) {
  const keys = [];
  const source = pathPattern.replace(/:[^/]+/g, (m) => { keys.push(m.slice(1)); return "([^/]+)"; });
  routes.push({ regex: new RegExp(`^${source}$`), keys, render: renderFn });
}

export function registerFallback(renderFn) { fallback = renderFn; }
export function onRouteChange(fn) { onNavigate = fn; }

function currentPath() {
  const h = location.hash.replace(/^#/, "");
  return h || "/home";
}

function match(path) {
  for (const r of routes) {
    const m = r.regex.exec(path);
    if (m) {
      const params = {};
      r.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
      return { render: r.render, params };
    }
  }
  return null;
}

function render() {
  const path = currentPath();
  const hit = match(path);
  if (onNavigate) onNavigate(path);
  if (mountTarget) {
    if (hit) hit.render(mountTarget, hit.params);
    else if (fallback) fallback(mountTarget, {});
  }
}

export function start(target) {
  mountTarget = target;
  window.addEventListener("hashchange", render);
  render();
}

export function navigate(path) {
  location.hash = path;
}
