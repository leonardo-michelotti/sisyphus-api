"""Vitrine e widget incorporável do MVP."""

# ruff: noqa: E501

from __future__ import annotations

import html
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from ..catalog import ALL_THINKERS, list_collections
from ..deps import DailyQuotes, Service
from ..errors import SisyphusError
from ..schemas import QuoteSelection, SelectionMode
from ..services.quote_selection import select_quote

router = APIRouter(tags=["site e widget"])

_STYLE = """
:root {
  color-scheme: dark;
  --bg: #0c0f12;
  --panel: #14191e;
  --panel-soft: #101419;
  --ink: #f3efe7;
  --muted: #a7adb5;
  --line: #303841;
  --line-strong: #48515b;
  --accent: #d4a85a;
  --accent-soft: #2a2419;
  --ok: #91b49a;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 78% 8%, rgba(212, 168, 90, .08), transparent 25rem),
    var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  text-rendering: optimizeLegibility;
}
a { color: inherit; }
a:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}
.skip-link {
  position: fixed;
  left: 16px;
  top: -80px;
  z-index: 20;
  background: var(--ink);
  color: var(--bg);
  padding: 10px 14px;
}
.skip-link:focus { top: 16px; }
.shell { width: min(1080px, calc(100% - 40px)); margin: 0 auto; padding: 24px 0 72px; }
.topnav {
  position: sticky;
  top: 14px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  margin-bottom: 72px;
  padding: 13px 16px;
  border: 1px solid rgba(72, 81, 91, .75);
  background: rgba(12, 15, 18, .88);
  backdrop-filter: blur(14px);
}
.brand { font: 600 18px Georgia, serif; text-decoration: none; letter-spacing: .02em; }
.links { display: flex; gap: 22px; flex-wrap: wrap; color: var(--muted); font-size: 14px; }
.links a { text-underline-offset: 4px; }
.topnav .links { margin: 0; }
.eyebrow {
  margin: 0;
  font-size: 11px;
  letter-spacing: .17em;
  text-transform: uppercase;
  color: var(--accent);
}
.hero-copy { max-width: 800px; }
h1 { font: 500 clamp(46px, 8vw, 86px)/.96 Georgia, serif; margin: 16px 0 24px; }
.lead { max-width: 720px; color: var(--muted); font-size: 19px; line-height: 1.65; }
.hero-links { display: flex; gap: 12px 24px; flex-wrap: wrap; margin-top: 28px; }
.text-link { color: var(--accent); text-underline-offset: 5px; }
.hero { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(250px, .75fr); gap: 56px; align-items: center; padding: 34px 0 82px; }
.still-life { position: relative; width: min(100%, 330px); height: 250px; justify-self: end; }
.slope { position: absolute; left: 18px; right: 10px; bottom: 58px; height: 1px; background: var(--line-strong); transform: rotate(-18deg); transform-origin: left; }
.stone { position: absolute; right: 72px; top: 48px; width: 82px; height: 82px; border: 1px solid var(--line-strong); border-radius: 50%; background: radial-gradient(circle at 36% 30%, #31363b, #111519 70%); box-shadow: 14px 18px 36px rgba(0, 0, 0, .35); }
.cup-ring { position: absolute; left: 30px; bottom: 12px; width: 108px; height: 108px; border: 1px solid rgba(212, 168, 90, .42); border-radius: 50%; box-shadow: inset 0 0 0 10px rgba(212, 168, 90, .025); }
.cigarette { position: absolute; right: 18px; bottom: 29px; width: 112px; height: 7px; background: #d8d2c7; transform: rotate(-9deg); }
.cigarette:after { content: ""; position: absolute; right: -8px; top: 0; width: 8px; height: 7px; background: var(--accent); }
.smoke { position: absolute; right: 2px; bottom: 57px; width: 34px; height: 70px; border-left: 1px solid rgba(167, 173, 181, .42); border-radius: 50%; transform: rotate(14deg); }
.proofs { display: flex; gap: 10px; flex-wrap: wrap; margin: 34px 0 0; padding: 0; list-style: none; }
.proofs li { border: 1px solid var(--line); padding: 8px 11px; color: var(--muted); font-size: 12px; }
.proofs li:first-child { color: var(--ok); border-color: rgba(145, 180, 154, .45); }
.builder {
  margin: 64px 0 24px;
  border: 1px solid var(--line-strong);
  background: var(--panel-soft);
}
.builder-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 22px 24px;
  border-bottom: 1px solid var(--line);
}
.builder-head h2 { margin: 7px 0 0; font: 500 25px/1.2 Georgia, serif; }
.builder-head p:last-child { max-width: 370px; margin: 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
.preview { min-height: 300px; background: var(--panel); }
.preview iframe { display: block; width: 100%; height: 300px; border: 0; }
.builder-controls { padding: 22px 24px 24px; border-top: 1px solid var(--line); }
.controls { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.field { display: grid; gap: 7px; color: var(--muted); font-size: 12px; }
select, input, button {
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 0;
  background: #0d1115;
  color: var(--ink);
  padding: 10px 12px;
  font: inherit;
}
button { cursor: pointer; border-color: var(--accent); }
button:hover { background: var(--accent-soft); }
.builder-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
  margin-top: 14px;
}
.check { display: flex; gap: 9px; align-items: center; color: var(--muted); font-size: 13px; }
.check input { width: 17px; min-height: 17px; accent-color: var(--accent); }
.generated { min-width: 0; }
.generated output {
  display: block;
  overflow: hidden;
  margin-top: 7px;
  color: var(--muted);
  font: 12px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.copy-wrap { display: flex; gap: 12px; align-items: center; }
.copy-status { min-width: 76px; color: var(--ok); font-size: 12px; }
.note { margin: 22px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
.section { padding: 78px 0; border-top: 1px solid var(--line); }
.section-head { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, .7fr); gap: 48px; align-items: end; }
.section h2 { max-width: 680px; margin: 10px 0 0; font: 500 clamp(34px, 5vw, 52px)/1.05 Georgia, serif; }
.section-intro { margin: 0; color: var(--muted); line-height: 1.7; }
.surface-grid, .integration-grid, .route-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 36px; }
.card { min-height: 230px; border: 1px solid var(--line); background: var(--panel); padding: 25px; }
.card-index { display: block; margin-bottom: 42px; color: var(--accent); font: 12px ui-monospace, monospace; }
.card h3 { margin: 0 0 12px; font: 500 23px Georgia, serif; }
.card p { margin: 0 0 22px; color: var(--muted); line-height: 1.6; }
.card a { color: var(--accent); text-underline-offset: 4px; }
.route-card { position: relative; min-height: 260px; }
.route-card strong { display: block; margin-bottom: 14px; color: var(--accent); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }
.route-card code { color: var(--ink); }
.route-card .route-status { margin-top: 28px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 12px; }
.code {
  display: block;
  overflow: auto;
  background: #090b0e;
  border: 1px solid var(--line);
  padding: 15px;
  color: #d7dbe2;
  font: 12px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace;
  white-space: pre-wrap;
}
.technical-note {
  display: grid;
  grid-template-columns: 1.2fr .8fr;
  gap: 38px;
  margin-top: 36px;
  padding: 28px;
  border: 1px solid var(--line);
  background: linear-gradient(120deg, var(--panel), var(--accent-soft));
}
.technical-note h3 { margin: 0; font: 500 26px/1.2 Georgia, serif; }
.technical-note p { margin: 0; color: var(--muted); line-height: 1.65; }
.quiet-section { display: grid; grid-template-columns: .7fr 1.3fr; gap: 70px; padding: 76px 0; border-top: 1px solid var(--line); }
.quiet-copy { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.quiet-copy p { margin: 0; color: var(--muted); line-height: 1.7; }
.quiet-copy strong { display: block; margin-bottom: 8px; color: var(--ink); font-weight: 500; }
.use-list { margin-top: 34px; border-top: 1px solid var(--line); }
.use-row { display: grid; grid-template-columns: 52px 160px 1fr; gap: 24px; align-items: start; padding: 24px 0; border-bottom: 1px solid var(--line); }
.use-row span { color: var(--accent); font: 12px ui-monospace, monospace; }
.use-row h3 { margin: 0; font: 500 20px Georgia, serif; }
.use-row p { margin: 0; color: var(--muted); line-height: 1.6; }
.use-row code { color: var(--ink); }
.footer { padding: 40px 0 10px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
.footer .links { margin-top: 16px; }
.widget { min-height: 100vh; display: grid; place-items: center; padding: 28px; background: var(--bg); }
.quote { width: min(720px, 100%); }
.quote blockquote { margin: 0; font: 400 clamp(25px, 5vw, 44px)/1.25 Georgia, serif; }
.author { margin-top: 24px; color: var(--accent); font-weight: 650; }
.context, .source { margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.45; }
.source { margin-top: 20px; font-size: 11px; }
.error { color: var(--muted); font: 20px/1.5 Georgia, serif; }
.empty { color: var(--muted); line-height: 1.6; }
.lineage-head { max-width: 820px; padding: 34px 0 52px; }
.lineage-head h1 { max-width: 760px; }
.lineage-form { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; max-width: 620px; margin-top: 34px; }
.lineage-form label { grid-column: 1 / -1; }
.lineage-form input { width: 100%; }
.thinker-suggestions { display: flex; gap: 8px 18px; flex-wrap: wrap; margin-top: 18px; color: var(--muted); font-size: 13px; }
.thinker-suggestions a { text-underline-offset: 4px; }
.lineage { display: grid; grid-template-columns: minmax(220px, .75fr) 130px minmax(360px, 1.25fr); gap: 24px; align-items: center; padding: 52px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.focus-node { border: 1px solid var(--accent); background: var(--accent-soft); padding: 26px; }
.focus-node .node-label, .ancestry-head span { display: block; margin-bottom: 13px; color: var(--muted); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
.focus-node h2 { margin: 0 0 18px; font: 500 30px/1.1 Georgia, serif; }
.node-source, .influence-source { color: var(--muted); font-size: 12px; text-underline-offset: 4px; }
.relation { display: grid; gap: 12px; color: var(--muted); font-size: 11px; line-height: 1.4; text-align: center; }
.relation:before { content: ""; height: 1px; background: linear-gradient(90deg, var(--accent), var(--line-strong)); }
.ancestry-head { display: flex; justify-content: space-between; gap: 18px; align-items: baseline; margin-bottom: 16px; }
.ancestry-head span { margin: 0; }
.ancestry-head strong { color: var(--accent); font: 500 14px ui-monospace, monospace; }
.influence-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 0; padding: 0; list-style: none; }
.influence-item { display: grid; gap: 10px; min-height: 104px; padding: 17px; border: 1px solid var(--line); background: var(--panel); }
.influence-name { font: 500 18px/1.25 Georgia, serif; text-underline-offset: 4px; }
.influence-name:hover { color: var(--accent); }
.lineage-note { max-width: 760px; margin: 24px 0 0; color: var(--muted); font-size: 13px; line-height: 1.65; }
.collection-head { max-width: 800px; padding: 34px 0 58px; }
.collection-head h1 { max-width: 760px; }
.collection-summary { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 28px; }
.collection-summary span { border: 1px solid var(--line); padding: 8px 11px; color: var(--muted); font-size: 12px; }
.collection-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 0 0 72px; }
.collection-card { display: grid; grid-template-rows: auto auto 1fr auto; min-height: 410px; border: 1px solid var(--line); background: var(--panel); padding: 26px; }
.collection-number { color: var(--accent); font: 12px ui-monospace, monospace; }
.collection-card h2 { margin: 22px 0 10px; font: 500 30px/1.1 Georgia, serif; }
.collection-description { margin: 0; color: var(--muted); line-height: 1.65; }
.collection-people { margin: 20px 0 0; color: var(--muted); font-size: 12px; line-height: 1.65; }
.collection-sample { margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--line); }
.collection-sample blockquote { margin: 0; font: 500 20px/1.4 Georgia, serif; }
.collection-sample cite { display: block; margin-top: 13px; color: var(--accent); font-size: 12px; font-style: normal; }
.collection-actions { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 26px; font-size: 13px; }
.collection-actions a { color: var(--accent); text-underline-offset: 4px; }
@media (max-width: 820px) {
  .hero { grid-template-columns: 1fr; }
  .still-life { justify-self: start; width: 280px; height: 190px; }
  .stone { top: 18px; }
  .controls { grid-template-columns: 1fr 1fr; }
  .surface-grid, .integration-grid, .route-grid { grid-template-columns: 1fr; }
  .card { min-height: 0; }
  .card-index { margin-bottom: 24px; }
  .section-head, .technical-note, .quiet-section { grid-template-columns: 1fr; gap: 28px; }
  .lineage { grid-template-columns: 1fr; align-items: start; }
  .relation { grid-template-columns: 70px 1fr; align-items: center; text-align: left; }
  .collection-grid { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .shell { width: min(100% - 28px, 1080px); padding-top: 14px; }
  .topnav { top: 8px; align-items: flex-start; margin-bottom: 52px; }
  .topnav .links { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }
  h1 { font-size: clamp(43px, 15vw, 62px); }
  .lead { font-size: 17px; }
  .builder { margin-top: 46px; }
  .builder-head { display: block; }
  .builder-head p:last-child { margin-top: 12px; }
  .controls, .builder-actions { grid-template-columns: 1fr; }
  .copy-wrap { justify-content: space-between; }
  .copy-wrap button { flex: 1; }
  .generated output { white-space: normal; overflow-wrap: anywhere; }
  .section { padding: 58px 0; }
  .quiet-copy { grid-template-columns: 1fr; }
  .use-row { grid-template-columns: 38px 1fr; gap: 12px; }
  .use-row p { grid-column: 2; }
  .lineage-form { grid-template-columns: 1fr; }
  .lineage-form label { grid-column: auto; }
  .lineage-form button { width: 100%; }
  .influence-list { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
"""


def _document(title: str, body: str, script: str = "") -> str:
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='theme-color' content='#0c0f12'>"
        "<meta name='description' content='Frases com fonte, contexto e uma URL pronta para incorporar.'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}{script}</body></html>"
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    options = "<option value=''>Todas as coleções</option>" + "".join(
        f"<option value='{item.slug}'"
        f"{' selected' if item.slug == 'existencia-e-absurdo' else ''}>"
        f"{html.escape(item.titulo)}</option>"
        for item in list_collections()
    )
    thinker_options = "".join(
        f"<option value='{html.escape(thinker)}'></option>" for thinker in ALL_THINKERS
    )
    body = f"""<a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
    <main class="shell" id="conteudo">
      <nav class="topnav" aria-label="Navegação principal">
        <a class="brand" href="/">Sisyphus</a>
        <div class="links"><a href="#gerador">Gerador</a><a href="/collections">Coleções</a>
          <a href="#usar">Como usar</a>
          <a href="/docs">API</a><a href="https://github.com/leonardo-michelotti/sisyphus-api">GitHub</a></div>
      </nav>
      <header class="hero">
        <div class="hero-copy"><p class="eyebrow">Café, silêncio e uma frase</p>
          <h1>Uma frase para atravessar o dia.</h1>
          <p class="lead">Escolha uma voz, defina o ritmo e deixe uma frase por perto.
          Numa nota, numa página ou no intervalo entre duas tarefas.</p>
          <div class="hero-links"><a class="text-link" href="#gerador">Montar o widget</a>
            <a class="text-link" href="/influences">Seguir uma influência</a></div>
        </div>
        <div class="still-life" aria-hidden="true"><span class="slope"></span>
          <span class="stone"></span><span class="cup-ring"></span>
          <span class="cigarette"></span><span class="smoke"></span></div>
      </header>
      <section class="builder" id="gerador" aria-labelledby="builder-title">
        <header class="builder-head"><div><p class="eyebrow">Gerador</p>
          <h2 id="builder-title">Escolha e copie.</h2></div>
          <p>A prévia é o próprio widget. O link abaixo leva exatamente o que aparece aqui.</p>
        </header>
        <div class="preview"><iframe id="preview" title="Prévia do widget"
          src="/widget?collection=existencia-e-absurdo&amp;mode=daily"></iframe></div>
        <div class="builder-controls"><div class="controls">
          <label class="field" for="collection">Coleção<select id="collection">{options}</select></label>
          <label class="field" for="mode">Ritmo<select id="mode">
            <option value="daily">Frase do dia</option><option value="random">Aleatória</option>
          </select></label>
          <label class="field" for="thinker">Pensador, opcional<input id="thinker"
            list="thinkers" placeholder="Ex.: Hannah Arendt" autocomplete="off"></label>
          <datalist id="thinkers">{thinker_options}</datalist>
          <label class="field" for="max-length">Tamanho máximo<select id="max-length">
            <option value="">Sem limite</option><option value="140">140 caracteres</option>
            <option value="220">220 caracteres</option><option value="320">320 caracteres</option>
          </select></label>
        </div><div class="builder-actions">
          <div class="generated"><label class="check" for="show-context">
            <input id="show-context" type="checkbox" checked>Mostrar contexto</label>
            <output id="generated-url" for="collection mode thinker max-length show-context"></output>
          </div><div class="copy-wrap"><button id="copy" type="button">Copiar link</button>
            <span class="copy-status" id="copy-status" role="status" aria-live="polite"></span>
          </div></div>
          <p class="note">O modo diário muda uma vez por dia. O aleatório muda a cada pedido.</p>
        </div>
      </section>
      <section class="quiet-section" aria-labelledby="choice-title"><div>
        <p class="eyebrow">Uma escolha simples</p><h2 id="choice-title">Diária ou aleatória.</h2>
      </div><div class="quiet-copy"><p><strong>Frase do dia</strong>Uma seleção revisada que
        permanece durante a data. Boa para deixar no canto de uma página.</p>
        <p><strong>Aleatória</strong>Uma consulta nova para quando a intenção é explorar.
        Fonte e licença continuam junto da frase.</p></div>
      </section>
      <section class="section" id="usar"><p class="eyebrow">Como usar</p>
        <h2>Uma URL basta.</h2><div class="use-list">
          <div class="use-row"><span>01</span><h3>Notion</h3>
            <p>Digite <code>/embed</code> e cole o link gerado.</p></div>
          <div class="use-row"><span>02</span><h3>Obsidian</h3>
            <p>Use o link dentro de um <code>iframe</code> na nota.</p></div>
          <div class="use-row"><span>03</span><h3>API</h3>
            <p>Consuma <code>GET /v1/quote-of-the-day</code> quando precisar do JSON.</p></div>
        </div>
      </section>
      <footer class="footer"><p>Só isso: uma frase, sua fonte e uma URL.</p>
        <nav class="links" aria-label="Links do rodapé"><a href="/docs">API</a>
          <a href="/collections">Coleções</a>
          <a href="/influences">Influências</a>
          <a href="https://github.com/leonardo-michelotti/sisyphus-api">GitHub</a></nav>
      </footer>
    </main>"""
    script = """<script>
const collection=document.getElementById('collection'),mode=document.getElementById('mode');
const thinker=document.getElementById('thinker'),maxLength=document.getElementById('max-length');
const showContext=document.getElementById('show-context'),preview=document.getElementById('preview');
const copy=document.getElementById('copy'),status=document.getElementById('copy-status');
const generated=document.getElementById('generated-url');
function path(){const p=new URLSearchParams({mode:mode.value});
if(collection.value)p.set('collection',collection.value);
if(thinker.value.trim())p.set('thinker',thinker.value.trim());
if(maxLength.value)p.set('max_length',maxLength.value);
p.set('show_context',showContext.checked?'true':'false');
return `${location.origin}/widget?${p}`;}
function update(){const value=path();preview.src=value;generated.textContent=value;status.textContent='';}
[collection,mode,thinker,maxLength,showContext].forEach(control=>control.addEventListener('change',update));
copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(path());
status.textContent='Link copiado.';}catch{status.textContent='Não foi possível copiar.';}});
generated.textContent=path();
</script>"""
    return HTMLResponse(_document("Sisyphus", body, script))


@router.get("/collections", response_class=HTMLResponse, include_in_schema=False)
async def collections_page(repository: DailyQuotes) -> HTMLResponse:
    """Apresenta os recortes editoriais e uma amostra da base curada."""
    collections = list_collections()
    cards: list[str] = []
    for index, collection in enumerate(collections, start=1):
        try:
            selection = repository.select(collection_slug=collection.slug)
            sample = (
                f"<blockquote>“{html.escape(selection.frase.texto)}”</blockquote>"
                f"<cite>{html.escape(selection.frase.autor)}</cite>"
            )
        except SisyphusError:
            sample = "<p class='empty'>Amostra diária indisponível.</p>"
        widget_query = urlencode(
            {"collection": collection.slug, "mode": "daily", "show_context": "true"}
        )
        people = ", ".join(collection.pensadores)
        cards.append(
            f"""<article class="collection-card">
              <span class="collection-number">{index:02d}</span><div>
                <h2>{html.escape(collection.titulo)}</h2>
                <p class="collection-description">{html.escape(collection.descricao)}</p>
                <p class="collection-people">{html.escape(people)}</p></div>
              <div class="collection-sample">{sample}</div>
              <nav class="collection-actions" aria-label="Ações de {html.escape(collection.titulo)}">
                <a href="/widget?{html.escape(widget_query)}">Abrir widget</a>
                <a href="/v1/quote-of-the-day?collection={html.escape(collection.slug)}">Ver JSON</a>
              </nav></article>"""
        )
    body = f"""<a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
    <main class="shell" id="conteudo"><nav class="topnav" aria-label="Navegação principal">
      <a class="brand" href="/">Sisyphus</a><div class="links"><a href="/">Gerador</a>
        <a href="/influences">Influências</a><a href="/docs">API</a>
        <a href="https://github.com/leonardo-michelotti/sisyphus-api">GitHub</a>
      </div></nav><header class="collection-head"><p class="eyebrow">Coleções editoriais</p>
      <h1>Dez maneiras de começar.</h1>
      <p class="lead">Cada coleção aproxima quatro vozes por uma pergunta comum. A amostra
      vem da base revisada e muda uma vez por dia.</p>
      <div class="collection-summary"><span>10 coleções</span><span>18 pensadores</span>
        <span>fontes preservadas</span></div></header>
      <section class="collection-grid" aria-label="Coleções disponíveis">{"".join(cards)}</section>
      <footer class="footer"><p>Escolha um recorte e deixe a frase por perto.</p>
        <nav class="links" aria-label="Links do rodapé"><a href="/">Voltar ao gerador</a>
          <a href="/influences">Influências</a><a href="/docs">API</a></nav>
      </footer></main>"""
    return HTMLResponse(_document("Coleções · Sisyphus", body))


@router.get("/influences", response_class=HTMLResponse, include_in_schema=False)
async def influences_page(service: Service, thinker: str = "Albert Camus") -> HTMLResponse:
    """Vitrine acessível do grafo direto, sem biblioteca JavaScript externa."""
    thinker_options = "".join(
        f"<option value='{html.escape(name)}'></option>" for name in ALL_THINKERS
    )
    suggestions = "".join(
        f"<a href='/influences?{html.escape(urlencode({'thinker': name}))}'>{html.escape(name)}</a>"
        for name in (
            "Albert Camus",
            "Simone de Beauvoir",
            "Friedrich Nietzsche",
            "Hannah Arendt",
            "Albert Einstein",
        )
    )
    try:
        graph = await service.get_influences(thinker)
        items = "".join(
            f"<li class='influence-item'><a class='influence-name' "
            f"href='/influences?{html.escape(urlencode({'thinker': node.nome}))}'>"
            f"{html.escape(node.nome)}</a><a class='influence-source' "
            f"href='{html.escape(node.url)}' target='_blank' rel='noopener noreferrer'>"
            f"Wikidata · {html.escape(node.qid)}</a></li>"
            for node in graph.influenciado_por
        )
        related = (
            f"<ol class='influence-list'>{items}</ol>"
            if items
            else """<p class='empty'>O Wikidata não registra influências diretas
        para esta personalidade.</p>"""
        )
        network = f"""<section class="lineage" aria-label="Influências intelectuais">
          <article class="focus-node"><span class="node-label">Pensador consultado</span>
            <h2>{html.escape(graph.pensador.nome)}</h2>
            <a class="node-source" href="{html.escape(graph.pensador.url)}" target="_blank"
              rel="noopener noreferrer">Wikidata · {html.escape(graph.pensador.qid)}</a>
          </article><div class="relation" aria-hidden="true">foi influenciado por</div>
          <div class="ancestry"><div class="ancestry-head"><span>Registros diretos</span>
            <strong>{len(graph.influenciado_por):02d}</strong></div>{related}</div></section>"""
    except SisyphusError as exc:
        network = f"<p class='error'>{html.escape(str(exc))}</p>"

    body = f"""<a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
    <main class="shell" id="conteudo"><nav class="topnav" aria-label="Navegação principal">
      <a class="brand" href="/">Sisyphus</a><div class="links"><a href="/">Gerador</a>
        <a href="/collections">Coleções</a><a href="/docs">API</a>
        <a href="https://github.com/leonardo-michelotti/sisyphus-api">GitHub</a>
      </div></nav><header class="lineage-head"><p class="eyebrow">Linhagem intelectual</p>
      <h1>Nenhuma ideia chega sozinha.</h1>
      <p class="lead">Escolha um nome e percorra as relações de “influenciado por” registradas
      no Wikidata. Cada pessoa abre o próximo caminho.</p>
      <form class="lineage-form" method="get"><label class="eyebrow" for="thinker">Pensador</label>
        <input id="thinker" name="thinker" list="thinker-list" value="{html.escape(thinker)}"
          autocomplete="off" required><datalist id="thinker-list">{thinker_options}</datalist>
        <button type="submit">Explorar</button></form>
      <nav class="thinker-suggestions" aria-label="Sugestões de pensadores">{suggestions}</nav>
      </header>{network}
      <p class="lineage-note">O mapa mostra apenas relações P737 declaradas no Wikidata.
      A ausência de uma conexão não significa ausência de influência histórica.</p>
      <footer class="footer"><p>Um passo leva ao próximo.</p><nav class="links"
        aria-label="Links do rodapé"><a href="/">Voltar ao gerador</a>
        <a href="/docs">API</a></nav></footer></main>"""
    return HTMLResponse(_document(f"Influências de {thinker} · Sisyphus", body))


def render_widget(selection: QuoteSelection, show_context: bool) -> str:
    quote = selection.frase
    context = ""
    if show_context:
        parts = [quote.categoria.value]
        if quote.obra:
            parts.append(quote.obra)
        if selection.colecao:
            parts.append(selection.colecao.titulo)
        context = f"<p class='context'>{html.escape(' · '.join(parts))}</p>"
    source = quote.fonte
    source_link = (
        f"<a href='{html.escape(source.url)}' target='_blank' rel='noopener noreferrer'>"
        f"{html.escape(source.fonte)}</a>"
        if source.url
        else html.escape(source.fonte)
    )
    body = f"""<main class="widget"><article class="quote">
      <blockquote>“{html.escape(quote.texto)}”</blockquote>
      <p class="author">{html.escape(quote.autor)}</p>{context}
      <p class="source">Fonte: {source_link} · {html.escape(source.licenca)}</p>
    </article></main>"""
    return _document(f"Frase de {quote.autor}", body)


@router.get("/widget", response_class=HTMLResponse, include_in_schema=False)
async def widget(
    service: Service,
    repository: DailyQuotes,
    mode: SelectionMode = SelectionMode.daily,
    thinker: Annotated[str | None, Query(description="Nome de uma personalidade")] = None,
    collection: Annotated[str | None, Query(description="Slug de uma coleção")] = None,
    show_context: bool = True,
    max_length: Annotated[int | None, Query(ge=40, le=1000)] = None,
) -> HTMLResponse:
    try:
        selection: QuoteSelection
        if mode is SelectionMode.daily:
            selection = repository.select(
                thinker=thinker,
                collection_slug=collection,
                max_length=max_length,
            )
        else:
            selection = await select_quote(
                service,
                mode=mode,
                thinker=thinker,
                collection_slug=collection,
                max_length=max_length,
            )
        response = HTMLResponse(render_widget(selection, show_context))
        response.headers["Cache-Control"] = (
            "public, max-age=3600" if mode is SelectionMode.daily else "no-store"
        )
        return response
    except SisyphusError as exc:
        body = f"<main class='widget'><p class='error'>{html.escape(str(exc))}</p></main>"
        return HTMLResponse(_document("Sisyphus", body), status_code=exc.status)
