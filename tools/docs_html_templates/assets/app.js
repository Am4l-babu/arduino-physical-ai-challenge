// DOMORA Docs — shared interactivity. No framework, no CDN: vanilla JS over
// static HTML, same discipline as studio/ (see docs/APP_PLAN.md).
(function () {
  "use strict";

  // ---- theme toggle (persisted, respects prefers-color-scheme by default) ----
  var THEME_KEY = "domora-docs-theme";
  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }
  var savedTheme = localStorage.getItem(THEME_KEY);
  if (savedTheme) applyTheme(savedTheme);

  function initThemeToggle() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme");
      var prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
      var effectiveCurrent = current || (prefersLight ? "light" : "dark");
      var next = effectiveCurrent === "dark" ? "light" : "dark";
      applyTheme(next);
      localStorage.setItem(THEME_KEY, next);
    });
  }

  // ---- reading progress bar ----
  function initProgress() {
    var bar = document.querySelector(".progress-rail__bar");
    if (!bar) return;
    function update() {
      var h = document.documentElement;
      var scrolled = h.scrollTop;
      var max = h.scrollHeight - h.clientHeight;
      var pct = max > 0 ? (scrolled / max) * 100 : 0;
      bar.style.width = pct + "%";
    }
    document.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  // ---- back-to-top ----
  function initToTop() {
    var btn = document.querySelector(".to-top");
    if (!btn) return;
    function update() { btn.classList.toggle("show", window.scrollY > 480); }
    document.addEventListener("scroll", update, { passive: true });
    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    update();
  }

  // ---- scroll-spy: highlight active TOC + minimap entry ----
  function initScrollSpy() {
    var headings = Array.prototype.slice.call(document.querySelectorAll(".doc h1[id], .doc h2[id], .doc h3[id], .doc h4[id]"));
    var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a, .minimap a"));
    if (!headings.length || !tocLinks.length) return;
    var linksById = {};
    tocLinks.forEach(function (a) {
      var id = a.getAttribute("href").slice(1);
      (linksById[id] = linksById[id] || []).push(a);
    });

    var current = null;
    function setActive(id) {
      if (id === current) return;
      current = id;
      tocLinks.forEach(function (a) { a.classList.remove("active"); });
      (linksById[id] || []).forEach(function (a) { a.classList.add("active"); });
    }

    var observer = new IntersectionObserver(
      function (entries) {
        var visible = entries.filter(function (e) { return e.isIntersecting; });
        if (visible.length) {
          visible.sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; });
          setActive(visible[0].target.id);
        }
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: [0, 1] }
    );
    headings.forEach(function (h) { observer.observe(h); });
    if (headings[0]) setActive(headings[0].id);
  }

  // ---- copy-to-clipboard on code blocks ----
  function initCopyButtons() {
    document.querySelectorAll(".code-block__copy").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pre = btn.closest(".code-block").querySelector("pre code");
        if (!pre) return;
        navigator.clipboard.writeText(pre.textContent).then(function () {
          var original = btn.textContent;
          btn.textContent = "Copied";
          btn.classList.add("copied");
          setTimeout(function () {
            btn.textContent = original;
            btn.classList.remove("copied");
          }, 1400);
        });
      });
    });
  }

  // ---- mermaid: render + raw-source toggle ----
  function initMermaid() {
    var blocks = document.querySelectorAll(".mermaid");
    if (!blocks.length || typeof mermaid === "undefined") return;
    var isLight = document.documentElement.getAttribute("data-theme") === "light" ||
      (!document.documentElement.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: light)").matches);
    mermaid.initialize({
      startOnLoad: false,
      theme: "base",
      themeVariables: isLight
        ? { background: "#ffffff", primaryColor: "#eaf3ff", primaryTextColor: "#14161b", primaryBorderColor: "#5eb1ff", lineColor: "#8891a0", secondaryColor: "#fff3e0", tertiaryColor: "#f3f4f7", fontFamily: "-apple-system, Segoe UI, sans-serif" }
        : { background: "#0b0d12", primaryColor: "#16192a", primaryTextColor: "#eef1f6", primaryBorderColor: "#5eb1ff", lineColor: "#6b7484", secondaryColor: "#231d12", tertiaryColor: "#12151c", fontFamily: "-apple-system, Segoe UI, sans-serif" },
    });
    mermaid.run({ nodes: blocks });
  }

  // ---- toggle raw mermaid source ----
  function initMermaidToggles() {
    document.querySelectorAll(".mermaid-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var src = btn.nextElementSibling;
        var showing = src.classList.toggle("show");
        btn.textContent = showing ? "Hide diagram source" : "View diagram source";
      });
    });
  }

  // ---- mobile sidebar drawer ----
  function initSidebarToggle() {
    var btn = document.getElementById("sidebar-toggle");
    var sidebar = document.querySelector(".layout__sidebar");
    if (!btn || !sidebar) return;
    btn.addEventListener("click", function () { sidebar.classList.toggle("open"); });
  }

  // ---- search: fetches the prebuilt search-index.json once, filters client-side ----
  function initSearch() {
    var inputs = document.querySelectorAll("#doc-search");
    if (!inputs.length) return;
    var index = null;

    function ensureIndex(cb) {
      if (index) return cb(index);
      fetch("search-index.json")
        .then(function (r) { return r.json(); })
        .then(function (data) { index = data; cb(index); })
        .catch(function () { index = []; cb(index); });
    }

    function escapeHtml(s) {
      return s.replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; });
    }

    inputs.forEach(function (input) {
      var results = input.closest(".search-box").querySelector(".search-results");
      if (!results) return;

      function render(query) {
        var q = query.trim().toLowerCase();
        if (!q) { results.classList.remove("show"); results.innerHTML = ""; return; }
        var hits = index
          .filter(function (item) { return item.text.toLowerCase().indexOf(q) !== -1; })
          .slice(0, 12);
        if (!hits.length) {
          results.innerHTML = '<a><span class="search-results__doc">No matches</span></a>';
          results.classList.add("show");
          return;
        }
        results.innerHTML = hits
          .map(function (item) {
            var idx = item.text.toLowerCase().indexOf(q);
            var start = Math.max(0, idx - 30);
            var snippet = (start > 0 ? "…" : "") + escapeHtml(item.text.slice(start, idx)) +
              "<mark>" + escapeHtml(item.text.slice(idx, idx + q.length)) + "</mark>" +
              escapeHtml(item.text.slice(idx + q.length, idx + q.length + 60)) + "…";
            return '<a href="' + item.href + '"><span class="search-results__doc">' + escapeHtml(item.doc) + " → " + escapeHtml(item.heading) +
              '</span>' + snippet + "</a>";
          })
          .join("");
        results.classList.add("show");
      }

      input.addEventListener("input", function () {
        ensureIndex(function () { render(input.value); });
      });
      input.addEventListener("focus", function () {
        ensureIndex(function () { if (input.value) render(input.value); });
      });
      document.addEventListener("click", function (e) {
        if (!results.contains(e.target) && e.target !== input) results.classList.remove("show");
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && inputs[0] && document.activeElement.tagName !== "INPUT") {
        e.preventDefault();
        inputs[0].focus();
      }
      if (e.key === "Escape") {
        document.querySelectorAll(".search-results").forEach(function (r) { r.classList.remove("show"); });
        document.activeElement.blur();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initThemeToggle();
    initProgress();
    initToTop();
    initScrollSpy();
    initCopyButtons();
    initMermaid();
    initMermaidToggles();
    initSidebarToggle();
    initSearch();
  });
})();
