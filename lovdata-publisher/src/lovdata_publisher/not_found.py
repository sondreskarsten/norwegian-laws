"""Generate the GitHub Pages recovery page for missing corpus URLs."""
from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlsplit

SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"


def generate_not_found_page(
    site_dir: str = "_site", *, site_index=None, site_base: str = SITE_BASE,
) -> str:
    """Write 404.html with navigation that also works at deeply nested URLs.

    GitHub Pages serves this document at the originally requested URL. Therefore
    links use the configured project's absolute path, never relative ``../``.
    Optional per-document history links come only from already generated pages.
    A missing page is not evidence of repeal or of a particular repeal date.
    """
    parsed = urlsplit(site_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("site_base must be an HTTP(S) site URL without a query or fragment")
    base_path = parsed.path.rstrip("/") + "/"
    site = Path(site_dir)
    root = site.resolve()
    history = {}
    for refid, relative in sorted(getattr(site_index, "historie", {}).items()):
        target = site / relative
        if (relative.startswith("historie/") and relative.endswith(".html")
                and target.is_file() and root in target.resolve().parents):
            history[refid] = base_path + relative

    def link(path: str) -> str:
        return html.escape(base_path + path, quote=True)

    config = json.dumps({"base": base_path, "history": history}, ensure_ascii=False)
    # Keep serialized strings inside their script element even for unusual slugs.
    config = config.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    page = r"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<title>Siden finnes ikke — Norges Lover og Forskrifter</title>
<style>
* { box-sizing: border-box; }
body { max-width: 960px; margin: 0 auto; padding: 1.5rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; line-height: 1.6; color: #212529; background: #fff; }
a { color: #1864ab; text-underline-offset: 3px; }
a:hover { color: #124b81; }
a:focus-visible { outline: 3px solid #2780e3; outline-offset: 4px; border-radius: 2px; }
nav { display: flex; gap: 1rem; justify-content: space-between; align-items: center; background: #f8f9fa; padding: .65rem 1rem; border-radius: 4px; font-size: .9rem; }
nav a { text-decoration: none; }
.brand { font-weight: 600; }
main { padding-top: 2rem; }
.status { margin: 0 0 .4rem; font-size: .8rem; font-weight: 700; letter-spacing: .12em; color: #1864ab; }
h1 { margin: 0 0 .8rem; font-size: clamp(1.8rem, 5vw, 2.35rem); line-height: 1.2; letter-spacing: -.025em; }
.lead { max-width: 44rem; margin: 0 0 1.5rem; color: #495057; font-size: 1.05rem; }
.context { margin: 1.5rem 0; padding: 1rem 1.2rem; background: #f1f7fd; border-left: 3px solid #2780e3; border-radius: 4px; }
.context h2 { margin: 0 0 .3rem; font-size: .9rem; font-weight: 600; color: #495057; }
.context code { display: block; font-size: 1.08rem; font-weight: 600; overflow-wrap: anywhere; }
.context p { margin: .6rem 0; }
.context ul { margin: .7rem 0 0; padding-left: 1.2rem; }
.context li { margin: .2rem 0; }
.routes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin: 1.5rem 0; }
.route { padding: 1rem 1.2rem; border: 1px solid #dee2e6; border-radius: 5px; }
.route h2 { margin: 0 0 .35rem; font-size: 1.05rem; }
.route p { margin: 0; color: #495057; font-size: .93rem; }
.note { max-width: 48rem; color: #495057; font-size: .92rem; }
details { font-size: .85rem; color: #6c757d; margin-top: 1.5rem; }
summary { cursor: pointer; }
#requested-path { display: block; margin-top: .5rem; overflow-wrap: anywhere; }
footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: .85rem; }
[hidden] { display: none !important; }
@media (max-width: 560px) { body { padding: 1rem; } main { padding-top: 1.5rem; } nav { align-items: flex-start; } .routes { grid-template-columns: 1fr; gap: .75rem; } }
</style>
</head>
<body>
<nav aria-label="Hovedmeny"><a class="brand" href="__HOME__">Norges Lover og Forskrifter</a><a href="__SEARCH__">Søk</a></nav>
<main>
<p class="status">404 · SIDEN FINNES IKKE</p>
<h1>Vi finner ikke denne siden</h1>
<p class="lead">Lenken kan være utdatert, eller dokumentet kan ha falt ut av samlingen med gjeldende lover og forskrifter. Her er noen veier videre.</p>

<section id="document-context" class="context" aria-labelledby="document-heading" hidden>
<h2 id="document-heading">Dokumentet i lenken</h2>
<code id="document-refid"></code>
<p>Bruk identifikatoren når du søker, eller prøv dokumentets sider hos Lovdata.</p>
<ul>
<li><a id="source-current">Åpne dokumentet hos Lovdata</a></li>
<li><a id="source-archive">Se etter historisk tekst hos Lovdata</a></li>
<li><a id="stored-copies">Tidligere lagrede utgaver på GitHub</a></li>
<li id="document-history-item" hidden><a id="document-history">Se dokumentets endringshistorikk her</a></li>
</ul>
<p class="note">GitHub viser tidligere publiserte kopier, ikke bekreftede rettslige versjoner.</p>
</section>

<div class="routes" aria-label="Finn fram">
<section class="route"><h2><a href="__SEARCH__">Søk i lover og forskrifter →</a></h2><p>Finn gjeldende dokumenter etter navn, korttittel eller identifikator.</p></section>
<section class="route"><h2><a href="__HISTORY__">Versjoner og historikk →</a></h2><p>Se oversikten over tidligere versjoner og veier til endringshistorikk.</p></section>
<section class="route"><h2><a href="__HOME__">Gå til forsiden →</a></h2><p>Bla i samlingen etter departement eller rettsområde.</p></section>
<section class="route"><h2><a href="https://lovdata.no/">Søk hos Lovdata →</a></h2><p>Finn kildeteksten og informasjon om dokumentets status.</p></section>
</div>

<p class="note">Opphevede dokumenter kan finnes i Lovdatas historiske arkiv selv om de ikke lenger er med i denne samlingen. En manglende side her fastslår ikke om eller når et dokument er opphevet.</p>
<details id="path-details" hidden><summary>Adressen du forsøkte å åpne</summary><code id="requested-path"></code></details>
</main>
<footer>Datakilde: <a href="https://lovdata.no/">Lovdata</a>. Denne nettsiden er ikke en autoritativ rettskilde.</footer>
<script id="recovery-config" type="application/json">__CONFIG__</script>
<script>
(function () {
  "use strict";
  var config = JSON.parse(document.getElementById("recovery-config").textContent);
  var path;
  try { path = decodeURIComponent(window.location.pathname); }
  catch (_) { path = window.location.pathname; }
  document.getElementById("requested-path").textContent = path;
  document.getElementById("path-details").hidden = false;
  if (!path.startsWith(config.base)) return;
  var relative = path.slice(config.base.length);
  var corpus = relative.match(/^(lover\/lov|forskrifter\/forskrift)-(\d{4}-\d{2}-\d{2}(?:-\d+)?)(?:\.html|\.md)?\/?$/);
  var paragraph = relative.match(/^historikk\/(lov|forskrift)-(\d{4}-\d{2}-\d{2}(?:-\d+)?)\/(?:para-[\w-]+\.html)?$/);
  var match = corpus || paragraph;
  if (!match) return;
  var kind = corpus ? (match[1] === "lover/lov" ? "lov" : "forskrift") : match[1];
  var refid = kind + "/" + match[2];
  var namespace = kind === "lov" ? "NL" : "SF";
  var archive = kind === "lov" ? "NLO" : "SFO";
  document.getElementById("document-refid").textContent = refid;
  document.getElementById("source-current").href = "https://lovdata.no/dokument/" + namespace + "/" + refid;
  document.getElementById("source-archive").href = "https://lovdata.no/dokument/" + archive + "/" + refid;
  var savedFile = (kind === "lov" ? "lover/lov-" : "forskrifter/forskrift-") + match[2] + ".md";
  document.getElementById("stored-copies").href = "https://github.com/sondreskarsten/norwegian-laws/commits/main/" + savedFile;
  if (Object.prototype.hasOwnProperty.call(config.history, refid)) {
    document.getElementById("document-history").href = config.history[refid];
    document.getElementById("document-history-item").hidden = false;
  }
  document.getElementById("document-context").hidden = false;
}());
</script>
</body>
</html>
"""
    page = page.replace("__HOME__", link("index.html")).replace("__SEARCH__", link("book/sok.html"))
    page = page.replace("__HISTORY__", link("book/versjoner.html")).replace("__CONFIG__", config)
    site.mkdir(parents=True, exist_ok=True)
    output = site / "404.html"
    output.write_text(page, encoding="utf-8", newline="\n")
    return str(output)
