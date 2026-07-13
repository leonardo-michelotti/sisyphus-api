# Arquitetura — como o sisyphus funciona

Explica o **fluxo de uma requisição** e a responsabilidade de cada camada do
código já implementado em `src/sisyphus/`. Para o *porquê* de cada decisão, ver
`DECISIONS.md`; para o detalhe técnico das fontes, `PILARES_TECNICOS.md`.

## Visão em uma frase

Dado o nome de um pensador, o serviço resolve a entidade, busca **biografia no
Wikidata** e **frases no Wikiquote** em paralelo, e devolve um perfil único em
JSON — com atribuição das fontes e semântica HTTP correta.

## Fluxo de `GET /thinkers/{nome}`

```
GET /thinkers/camus?frases=3
        │
   1. router (routers/thinkers.py)      camada HTTP fina: valida query params
        │
   2. ThinkerService.get_profile()      orquestra o perfil
        │
        ├─ 2a. WikiquoteClient.resolve("camus")
        │        list=search  → 1ª hit = "Albert Camus"
        │        pageprops    → wikibase_item = Q34670
        │        → (titulo="Albert Camus", qid="Q34670")
        │
        ├─ 2b. asyncio.gather(   ← as duas fontes EM PARALELO (ADR-004)
        │        WikidataClient.get_profile("Q34670")        → bio + obras
        │        WikiquoteClient.get_quotes("Albert Camus")  → frases
        │      )
        │
   3. monta ThinkerProfile (bio + amostra de frases + atribuição)
        │
   4. FastAPI serializa via Pydantic → JSON
```

O QID que amarra tudo vem **da própria página do Wikiquote** (passo 2a), então
bio e frases referem-se garantidamente à mesma entidade (ADR-018).

## Camadas e responsabilidades (ADR-006)

| Camada | Arquivo(s) | Responsabilidade |
|---|---|---|
| **routers** | `routers/thinkers.py`, `routers/health.py` | Só HTTP: valida entrada, chama o service. Sem lógica de negócio. |
| **services** | `services/thinker_service.py` | Regra "perfil = bio + frases, concorrente, tolerando falha parcial". |
| **clients** | `clients/wikiquote.py`, `clients/wikidata.py` | Como falar com **uma** fonte. Trocar/adicionar fonte fica contido aqui. |
| **schemas** | `schemas.py` | Contrato Pydantic (valida saída **e** gera o Swagger). |

Suporte transversal:

| Módulo | Papel |
|---|---|
| `config.py` | Settings via env (`SISYPHUS_*`), sem segredo/flag no código (ADR-008). |
| `errors.py` | Erros de domínio tipados → resposta `application/problem+json` (ADR-007). |
| `dates.py` | Converte `time`/`precision` do Wikidata (trata AEC, século, ano). |
| `cache.py` | `TTLCache` em memória (ADR-005). |
| `deps.py` | Injeta o `ThinkerService` montado no lifespan. |
| `main.py` | App factory + lifespan (cria `httpx.AsyncClient` compartilhado) + CORS. |

## As duas fontes (o núcleo)

**Wikiquote → frases.** Busca o HTML já **renderizado** (`action=parse&
prop=text`) e a função pura `parse_quotes` caminha o DOM com lxml: cada
`<ul><li>` é uma frase; o título da seção vira a **categoria**
(`verificada` / `obra` / `atribuida`); uma **denylist** descarta seções que não
são frases do autor (`Sobre`, `Ligações externas`, …). Usa-se HTML e não regex
sobre wikitext porque o MediaWiki já expandiu templates e resolveu wikilinks
(ADR-016).

**Wikidata → biografia.** Duas chamadas à REST `wbgetentities` (ADR-017):
1. Claims cruas do QID (nascimento, ocupação, obras… como referências a outros
   QIDs) + descrição + labels.
2. Um **batch** resolve esses QIDs referenciados em nomes legíveis (pt→en).

A função pura `build_thinker` monta o modelo tratando os casos de borda
validados: data AEC/parcial via `precision`, rank `preferred` em valores
conflitantes, e **label ausente é omitido** (nunca vaza QID cru).

## Comportamentos transversais

- **Concorrência:** um `httpx.AsyncClient` único (criado no lifespan) para todas
  as chamadas; bio e frases buscadas com `asyncio.gather`.
- **Cache TTL (24h):** a 2ª requisição do mesmo pensador não bate nas fontes.
  Chaves: `resolve:<nome>`, `profile:<qid>`, `quotes:<titulo>`.
- **Semântica HTTP (ADR-007):** pensador inexistente → **404**; fonte upstream
  fora/expira → **502/504**; corpo sempre `problem+json`.
- **Perfil parcial:** se a bio vem mas as frases falham, retorna o perfil só com
  a biografia + um campo `aviso` (em vez de derrubar a resposta inteira).
- **Atribuição (ADR-015):** cada frase carrega sua fonte (Wikiquote, CC BY-SA);
  o perfil credita Wikidata (CC0) e Wikiquote no nível-topo.

## Testes

14 testes em `tests/` exercitam as **funções puras** (`parse_quotes`,
`build_thinker`, `parse_wikidata_time`) com **fixtures reais salvas**
(`tests/fixtures/`) — não tocam a rede, rodam em segundos. Pendente: testes dos
clients com `respx` (mock HTTP) para cobrir a camada de rede.

## Rodar

```bash
source .venv/bin/activate
uvicorn sisyphus.main:app --reload      # Swagger interativo em /docs
```

Endpoints: `/thinkers/{nome}`, `/thinkers/{nome}/quotes`, `/search?q=`,
`/health`.
