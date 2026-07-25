#!/usr/bin/env python3
"""Renders docs/*.md into the interactive HTML doc site at docs/html/.

The Markdown files stay the source of truth (edited by hand, same as always);
this script is the one-way build step that turns them into the browsable
site. Re-run it after editing any docs/*.md:

    python tools/build_docs_html.py

Deliberately not part of hub/'s stdlib-only runtime (CLAUDE.md's stdlib rule
scopes to hub/ core) — this is a docs-tooling script, run on a dev machine,
never on the UNO Q. Needs `pip install markdown-it-py` (already present in
this environment).
"""
from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = DOCS / "html"
ICON_SRC = ROOT / "mobile" / "assets" / "icon" / "icon.png"


@dataclass
class DocSpec:
    src: str
    slug: str
    title: str
    description: str
    icon: str


DOC_SPECS = [
    DocSpec(
        "DOMORA_SPEC.md", "spec", "Engineering Specification",
        "The full system design: architecture, hardware tiers, safety framework, "
        "cybersecurity, and the adversarial self-review.",
        "🏛️",
    ),
    DocSpec(
        "APP_PLAN.md", "app-plan", "App Build Plan",
        "How DOMORA Studio (web) and DOMORA Mobile (Flutter) got built — phased, "
        "each phase verified against the real running hub before the next started.",
        "📱",
    ),
    DocSpec(
        "BOM_ORDER.md", "bom-order", "Bill of Materials",
        "The real parts list for the competition build — what was ordered, why, "
        "and what got rejected along the way.",
        "🧾",
    ),
    DocSpec(
        "AGENTS.md", "agents", "Agent Instructions",
        "Working rules for any AI-assisted session on this repo: the loop, the "
        "hard rules, and the checklist before ending a turn.",
        "🤖",
    ),
]


def slugify(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)  # inline code
    text = re.sub(r"[*_]{1,2}([^*_]*)[*_]{1,2}", r"\1", text)  # bold/italic
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text or "section"


def strip_md(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[*_]{1,2}([^*_]*)[*_]{1,2}", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.strip()


class DocRenderer:
    """One instance per document — holds the heading registry / slug state
    that the overridden render rules need to share across the token walk."""

    def __init__(self) -> None:
        self.md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
        self.headings: list[dict] = []
        self._slug_counts: dict[str, int] = {}
        self._id_stack: list[str] = []
        self.md.renderer.rules["heading_open"] = self._heading_open
        self.md.renderer.rules["heading_close"] = self._heading_close
        self.md.renderer.rules["fence"] = self._fence

    def _heading_open(self, tokens, idx, options, env):
        token = tokens[idx]
        inline = tokens[idx + 1]
        raw_slug = slugify(inline.content)
        n = self._slug_counts.get(raw_slug, 0)
        slug = raw_slug if n == 0 else f"{raw_slug}-{n}"
        self._slug_counts[raw_slug] = n + 1
        self._id_stack.append(slug)
        self.headings.append({"level": token.tag, "id": slug, "text": strip_md(inline.content)})
        return f'<{token.tag} id="{slug}">'

    def _heading_close(self, tokens, idx, options, env):
        tag = tokens[idx].tag
        slug = self._id_stack.pop()
        return f'<a href="#{slug}" class="heading-anchor" aria-label="Link to this section">#</a></{tag}>\n'

    def _fence(self, tokens, idx, options, env):
        token = tokens[idx]
        info = (token.info or "").strip()
        lang = info.split()[0] if info else "text"
        code = token.content
        if lang == "mermaid":
            escaped = html.escape(code)
            return (
                '<div class="mermaid-wrap">'
                f'<div class="mermaid">{escaped}</div>'
                '<button class="mermaid-toggle" type="button">View diagram source</button>'
                f'<pre class="mermaid-src">{escaped}</pre>'
                "</div>\n"
            )
        escaped = html.escape(code)
        lang_label = html.escape(lang)
        return (
            '<div class="code-block">'
            '<div class="code-block__bar">'
            f'<span class="code-block__lang">{lang_label}</span>'
            '<button class="code-block__copy" type="button">Copy</button>'
            "</div>"
            f'<pre><code class="language-{lang_label}">{escaped}</code></pre>'
            "</div>\n"
        )

    def render(self, markdown_text: str) -> tuple[str, list[dict], str]:
        tokens = self.md.parse(markdown_text)
        title = ""
        for i, tok in enumerate(tokens):
            if tok.type == "heading_open" and tok.tag == "h1":
                title = strip_md(tokens[i + 1].content)
                del tokens[i : i + 3]
                break
        body = self.md.renderer.render(tokens, self.md.options, {})
        body = body.replace("<table>", '<div class="table-scroll">\n<table>')
        body = body.replace("</table>", "</table>\n</div>")
        return body, self.headings, title


def build_toc(headings: list[dict]) -> str:
    """h1 (section dividers, after the doc's own title h1 is stripped) and
    h2 both read as top-level TOC entries; h3/h4 nest under the latest one."""
    items: list[str] = []
    stack_level = None  # tracks current nesting for indentation classes only
    out = ['<ul class="toc">']
    open_levels = []
    for h in headings:
        level = h["level"]
        depth = {"h1": 2, "h2": 2, "h3": 3, "h4": 4}.get(level, 2)
        cls = f"lvl-{depth}"
        out.append(f'<li class="{cls}"><a href="#{h["id"]}">{html.escape(h["text"])}</a></li>')
    out.append("</ul>")
    return "\n".join(out)


def build_minimap(headings: list[dict]) -> str:
    top = [h for h in headings if h["level"] in ("h1", "h2")]
    if not top:
        return ""
    items = "\n".join(
        f'<li><a href="#{h["id"]}">{html.escape(h["text"][:40])}</a></li>' for h in top
    )
    return f'<div class="minimap"><div class="minimap__label">On this page</div><ul>{items}</ul></div>'


def read_template(name: str) -> str:
    return (Path(__file__).parent / "docs_html_templates" / name).read_text(encoding="utf-8")


def render_page(spec: DocSpec, body: str, toc: str, minimap: str, nav_html: str, word_count: int) -> str:
    tpl = read_template("doc.html")
    return (
        tpl.replace("{{TITLE}}", html.escape(spec.title))
        .replace("{{DESCRIPTION}}", html.escape(spec.description))
        .replace("{{ICON}}", spec.icon)
        .replace("{{NAV}}", nav_html)
        .replace("{{TOC}}", toc)
        .replace("{{MINIMAP}}", minimap)
        .replace("{{BODY}}", body)
        .replace("{{WORDS}}", f"{word_count:,}")
        .replace("{{SLUG}}", spec.slug)
        .replace("{{SRC}}", spec.src)
    )


def build_nav(active_slug: str) -> str:
    links = ['<a href="index.html"' + (' class="active"' if active_slug == "index" else "") + ">Home</a>"]
    for spec in DOC_SPECS:
        cls = ' class="active"' if spec.slug == active_slug else ""
        links.append(f'<a href="{spec.slug}.html"{cls}>{spec.title}</a>')
    return "\n".join(links)


def build_index(cards_meta: list[dict]) -> str:
    tpl = read_template("index.html")
    cards = []
    for m in cards_meta:
        cards.append(
            f"""<div class="doc-card">
  <a class="stretched" href="{m['slug']}.html" aria-label="Open {html.escape(m['title'])}"></a>
  <span class="doc-card__icon">{m['icon']}</span>
  <h3>{html.escape(m['title'])}</h3>
  <p>{html.escape(m['description'])}</p>
  <div class="doc-card__meta"><span>{m['words']:,} words</span><span>{m['headings']} sections</span></div>
  <span class="doc-card__cta">Read <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
</div>"""
        )
    return tpl.replace("{{CARDS}}", "\n".join(cards)).replace("{{NAV}}", build_nav("index"))


def main() -> None:
    if OUT.exists():
        for item in OUT.iterdir():
            if item.name == "vendor":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "vendor").mkdir(parents=True, exist_ok=True)

    # assets/style.css and assets/app.js are hand-authored, sourced from
    # tools/docs_html_templates/assets/ and copied in fresh every build (the
    # OUT tree above is wiped except vendor/, so nothing survives otherwise).
    template_assets = Path(__file__).parent / "docs_html_templates" / "assets"
    for asset in template_assets.iterdir():
        shutil.copy(asset, OUT / "assets" / asset.name)
    if ICON_SRC.exists():
        shutil.copy(ICON_SRC, OUT / "assets" / "icon.png")

    search_index: list[dict] = []
    cards_meta: list[dict] = []

    for spec in DOC_SPECS:
        src_path = DOCS / spec.src
        markdown_text = src_path.read_text(encoding="utf-8")
        renderer = DocRenderer()
        body, headings, _doc_title = renderer.render(markdown_text)
        toc = build_toc(headings)
        minimap = build_minimap(headings)
        word_count = len(re.sub(r"<[^>]+>", " ", body).split())

        # search index: one entry per heading section (heading text + the
        # plain-text words until the next heading), used by assets/app.js.
        sections = re.split(r'(<h[1-4] id="[^"]+">)', body)
        current_heading = spec.title
        current_id = ""
        buf = ""
        for chunk in sections:
            m = re.match(r'<h[1-4] id="([^"]+)">', chunk)
            if m:
                if current_id:
                    text = re.sub(r"<[^>]+>", " ", buf)
                    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
                    if text:
                        search_index.append(
                            {"doc": spec.title, "heading": current_heading, "href": f"{spec.slug}.html#{current_id}", "text": f"{current_heading} {text}"[:400]}
                        )
                current_id = m.group(1)
                buf = ""
            else:
                heading_text_match = re.search(r"^(.*?)<a href", chunk)
                buf += chunk
        if current_id:
            text = re.sub(r"<[^>]+>", " ", buf)
            text = re.sub(r"\s+", " ", html.unescape(text)).strip()
            if text:
                search_index.append({"doc": spec.title, "heading": current_heading, "href": f"{spec.slug}.html#{current_id}", "text": f"{current_heading} {text}"[:400]})
        for h in headings:
            search_index.append({"doc": spec.title, "heading": h["text"], "href": f"{spec.slug}.html#{h['id']}", "text": h["text"]})

        nav_html = build_nav(spec.slug)
        page = render_page(spec, body, toc, minimap, nav_html, word_count)
        (OUT / f"{spec.slug}.html").write_text(page, encoding="utf-8")
        cards_meta.append(
            {"slug": spec.slug, "title": spec.title, "description": spec.description, "icon": spec.icon, "words": word_count, "headings": len(headings)}
        )
        print(f"  wrote {spec.slug}.html  ({word_count:,} words, {len(headings)} headings)")

    (OUT / "search-index.json").write_text(json.dumps(search_index, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote search-index.json  ({len(search_index)} entries)")

    (OUT / "index.html").write_text(build_index(cards_meta), encoding="utf-8")
    print("  wrote index.html")


if __name__ == "__main__":
    main()
