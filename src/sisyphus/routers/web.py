"""Vitrine e widget incorporável do MVP."""

from __future__ import annotations

import html
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from ..catalog import list_collections
from ..deps import Service
from ..errors import SisyphusError
from ..schemas import QuoteSelection, SelectionMode
from ..services.quote_selection import select_quote

router = APIRouter(tags=["site e widget"])

_STYLE = """
:root{color-scheme:dark;--bg:#0d0f12;--panel:#15191f;--ink:#f2eee6;--muted:#a5abb4;
--line:#303640;--accent:#d4a85a}*{box-sizing:border-box}body{margin:0;background:var(--bg);
color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,sans-serif}a{color:inherit}
.shell{width:min(940px,calc(100% - 36px));margin:0 auto;padding:72px 0}
.eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h1{font:500 clamp(42px,8vw,78px)/.95 Georgia,serif;margin:16px 0 22px}
.lead{max-width:650px;color:var(--muted);font-size:19px;line-height:1.55}
.topnav{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:64px}
.brand{font:600 18px Georgia,serif;text-decoration:none}.topnav .links{margin:0}
.preview{margin:54px 0 32px;border:1px solid var(--line);background:var(--panel);min-height:300px}
.preview iframe{display:block;width:100%;height:300px;border:0}.controls{display:grid;
grid-template-columns:1fr 1fr auto;gap:12px}.controls label{font-size:12px;color:var(--muted)}
select,button{width:100%;margin-top:6px;border:1px solid var(--line);background:#101318;
color:var(--ink);padding:12px 14px;font:inherit}
button{width:auto;align-self:end;cursor:pointer;border-color:var(--accent)}
.links{display:flex;gap:22px;flex-wrap:wrap;margin-top:44px;color:var(--muted);font-size:14px}
.note{margin-top:28px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);
line-height:1.6}
.section{padding:72px 0;border-top:1px solid var(--line)}
.section h2{font:500 38px/1.1 Georgia,serif;
margin:10px 0 16px}.section-intro{max-width:650px;color:var(--muted);line-height:1.65}
.surface-grid,.integration-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;
margin-top:32px}.card{border:1px solid var(--line);background:var(--panel);padding:24px}
.card h3{font:500 22px Georgia,serif;margin:0 0 12px}
.card p{color:var(--muted);line-height:1.55;margin:0 0 20px}.card a{color:var(--accent)}
.code{display:block;overflow:auto;background:#090b0e;border:1px solid var(--line);padding:16px;
font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;color:#d7dbe2;white-space:pre-wrap}
.footer{padding:40px 0 10px;color:var(--muted);font-size:13px}
.widget{min-height:100vh;display:grid;place-items:center;padding:28px;background:var(--bg)}
.quote{width:min(720px,100%)}blockquote{font:400 clamp(25px,5vw,44px)/1.25 Georgia,serif;
margin:0}.author{margin-top:24px;color:var(--accent);font-weight:650}.context,.source{margin-top:8px;
color:var(--muted);font-size:13px;line-height:1.45}.source{margin-top:20px;font-size:11px}
.error{color:var(--muted);font:20px/1.5 Georgia,serif}@media(max-width:680px){.shell{padding:44px 0}
.controls{grid-template-columns:1fr}.controls button{width:100%}}
.graph-head{display:flex;justify-content:space-between;gap:24px;align-items:end;margin-bottom:48px}
.graph-form{display:flex;gap:10px}.graph-form input{border:1px solid var(--line);
background:#101318;color:var(--ink);padding:12px 14px;font:inherit}
.network{position:relative;display:grid;grid-template-columns:
minmax(180px,1fr) minmax(240px,1.4fr);gap:80px;align-items:center;padding:48px 0}
.network:before{content:"";position:absolute;left:35%;right:48%;top:50%;
border-top:1px solid var(--accent)}
.node{position:relative;border:1px solid var(--line);background:var(--panel);padding:20px;z-index:1}
.node small{display:block;color:var(--muted);margin-top:7px}.node.root{border-color:var(--accent)}
.influences{display:grid;gap:12px}.empty{color:var(--muted);line-height:1.6}
@media(max-width:680px){.topnav{align-items:flex-start;margin-bottom:42px}
.topnav .links{display:grid;
gap:10px}.surface-grid,.integration-grid{grid-template-columns:1fr}.section{padding:52px 0}
.graph-head{display:block}.graph-form{margin-top:24px}
.network{grid-template-columns:1fr;gap:28px}.network:before{left:50%;right:auto;top:115px;
height:40px;border-top:0;border-left:1px solid var(--accent)}}
"""


def _document(title: str, body: str, script: str = "") -> str:
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}{script}</body></html>"
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    options = "".join(
        f"<option value='{item.slug}'>{html.escape(item.titulo)}</option>"
        for item in list_collections()
    )
    body = f"""<main class="shell">
      <nav class="topnav" aria-label="Navegação principal"><a class="brand" href="/">Sisyphus</a>
        <div class="links"><a href="#produto">Produto</a><a href="#integrar">Como usar</a>
          <a href="/docs">API</a><a href="/influences">Influências</a></div></nav>
      <p class="eyebrow">Frases, contexto e proveniência</p>
      <h1>Frases com contexto para seu espaço digital.</h1>
      <p class="lead">Escolha uma coleção, defina o ritmo e incorpore uma frase de filósofos,
      cientistas, sociólogos e escritores no Notion, Obsidian, em um site ou em seu produto.</p>
      <div class="preview"><iframe id="preview" title="Prévia do widget"
        src="/widget?collection=existencia-e-absurdo&mode=daily"></iframe></div>
      <div class="controls">
        <label>Coleção<select id="collection">{options}</select></label>
        <label>Ritmo<select id="mode"><option value="daily">Frase do dia</option>
          <option value="random">Aleatória</option></select></label>
        <button id="copy" type="button">Copiar link</button>
      </div>
      <p class="note">A frase do dia permanece estável durante a data UTC. O modo aleatório
      escolhe uma nova frase a cada requisição e não é armazenado em cache.</p>
      <section class="section" id="produto"><p class="eyebrow">Três superfícies</p>
        <h2>Um núcleo, diferentes formas de explorar.</h2>
        <p class="section-intro">A API, o widget e o mapa compartilham as mesmas fontes abertas
        e preservam a atribuição do conteúdo.</p><div class="surface-grid">
          <article class="card"><h3>Widget</h3><p>Uma URL pronta para incorporar, com coleção,
          ritmo e contexto configuráveis.</p><a href="#integrar">Ver integrações</a></article>
          <article class="card"><h3>API REST</h3><p>Contratos versionados, erros RFC 9457,
          cache HTTP e documentação OpenAPI.</p><a href="/docs">Abrir Swagger</a></article>
          <article class="card"><h3>Influências</h3><p>Relações intelectuais diretas declaradas
          no Wikidata, sem inferências históricas ocultas.</p>
          <a href="/influences">Explorar mapa</a></article>
        </div></section>
      <section class="section" id="integrar"><p class="eyebrow">Como usar</p>
        <h2>Comece com uma URL.</h2><div class="integration-grid">
          <article class="card"><h3>Notion</h3><p>Cole o link do widget e escolha a opção de
          incorporação.</p><code class="code">/widget?mode=daily</code></article>
          <article class="card"><h3>Obsidian</h3><p>Use um iframe HTML em uma nota que permita
          conteúdo incorporado.</p><code class="code">&lt;iframe src=&quot;https://SEU-DOMINIO/widget?mode=daily&quot;&gt;&lt;/iframe&gt;</code></article>
          <article class="card"><h3>Sites e automações</h3>
          <p>Consuma o JSON ou incorpore o widget sem
          dependências no front-end.</p><code class="code">GET /v1/quote-of-the-day</code></article>
        </div></section>
      <footer class="footer"><nav class="links"><a href="/v1/collections">Coleções em JSON</a>
        <a href="https://github.com/leonardo-michelotti/sisyphus-api">Código no GitHub</a>
        <a href="/health">Estado do serviço</a></nav></footer></main>"""
    script = """<script>
const collection=document.getElementById('collection'),mode=document.getElementById('mode');
const preview=document.getElementById('preview'),copy=document.getElementById('copy');
function path(){const p=new URLSearchParams({collection:collection.value,mode:mode.value});
return `${location.origin}/widget?${p}`;} function update(){preview.src=path();}
collection.onchange=update;mode.onchange=update;copy.onclick=async()=>{
await navigator.clipboard.writeText(path());
copy.textContent='Link copiado';setTimeout(()=>copy.textContent='Copiar link',1600);};
</script>"""
    return HTMLResponse(_document("Sisyphus", body, script))


@router.get("/influences", response_class=HTMLResponse, include_in_schema=False)
async def influences_page(service: Service, thinker: str = "Albert Camus") -> HTMLResponse:
    """Vitrine acessível do grafo direto, sem biblioteca JavaScript externa."""
    try:
        graph = await service.get_influences(thinker)
        items = "".join(
            f"<a class='node' href='{html.escape(node.url)}' target='_blank' "
            f"rel='noopener noreferrer'>{html.escape(node.nome)}<small>{node.qid}</small></a>"
            for node in graph.influenciado_por
        )
        related = (
            items
            or """<p class='empty'>O Wikidata não registra influências diretas
        para esta personalidade.</p>"""
        )
        network = f"""<section class="network" aria-label="Influências intelectuais">
          <a class="node root" href="{html.escape(graph.pensador.url)}" target="_blank"
            rel="noopener noreferrer">{html.escape(graph.pensador.nome)}
            <small>Pensador consultado · {graph.pensador.qid}</small></a>
          <div class="influences">{related}</div></section>"""
    except SisyphusError as exc:
        network = f"<p class='error'>{html.escape(str(exc))}</p>"

    body = f"""<main class="shell"><header class="graph-head"><div>
      <p class="eyebrow">Linhagem intelectual</p><h1>Ideias também têm antepassados.</h1>
      <p class="lead">Relações diretas de “influenciado por” registradas no Wikidata.</p></div>
      <form class="graph-form" method="get"><label class="eyebrow" for="thinker">Pensador</label>
        <input id="thinker" name="thinker" value="{html.escape(thinker)}" required>
        <button type="submit">Explorar</button></form></header>{network}
      <p class="note">O mapa mostra apenas relações P737 declaradas no Wikidata. Ausência de uma
      conexão não significa ausência de influência histórica.</p>
      <nav class="links"><a href="/">Voltar ao gerador</a>
        <a href="/docs">Documentação da API</a></nav></main>"""
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
    mode: SelectionMode = SelectionMode.daily,
    thinker: Annotated[str | None, Query(description="Nome de uma personalidade")] = None,
    collection: Annotated[str | None, Query(description="Slug de uma coleção")] = None,
    show_context: bool = True,
) -> HTMLResponse:
    try:
        selection = await select_quote(
            service, mode=mode, thinker=thinker, collection_slug=collection
        )
        response = HTMLResponse(render_widget(selection, show_context))
        response.headers["Cache-Control"] = (
            "public, max-age=3600" if mode is SelectionMode.daily else "no-store"
        )
        return response
    except SisyphusError as exc:
        body = f"<main class='widget'><p class='error'>{html.escape(str(exc))}</p></main>"
        return HTMLResponse(_document("Sisyphus", body), status_code=exc.status)
