# Pilares técnicos — refinamento validado

Refinamento dos **dois pilares que destravam o resto** (ver `PLANEJAMENTO.md`).
Tudo aqui foi **testado contra as APIs reais** em 2026-07-03 com 5 autores de
perfis distintos: Aristóteles (antigo, obras em subseções), Albert Camus,
Friedrich Nietzsche, Clarice Lispector e Sun Tzu (antigo, dados esparsos).

Amostra de validação (frases extraídas por autor):

| Autor | Frases | Observação |
|---|---|---|
| Aristóteles | 56 | frases distribuídas em seções por obra |
| Albert Camus | 118 | `Verificadas` + obras + `Atribuídas` |
| Friedrich Nietzsche | 141 | tem seção-armadilha `Sobre` (excluída) |
| Clarice Lispector | 113 | frases longas, com `(...)` no original |
| Sun Tzu | 22 | página sem headings — frases no topo |

---

## Pilar 1 — Parsing do Wikiquote

### Decisão: HTML renderizado, não wikitext

Usar `action=parse&prop=text` (HTML já renderizado pelo MediaWiki) e parsear o
DOM com **lxml**. **Não** parsear o `wikitext` cru com regex.

**Por quê:** no HTML o MediaWiki já expandiu templates, resolveu wikilinks
(`[[amor|amar]]` → `<a>amar</a>`) e tratou toda a formatação. Regex sobre
wikitext teria que reimplementar isso e quebra por página. O HTML é estável e
uniforme entre autores (validado nos 5).

### Estrutura do HTML (constante entre autores)

```html
<div class="mw-heading mw-heading3"><h3 id="Verificadas">Verificadas</h3>…</div>
<ul><li>"A sabedoria consiste em não destruir o mundo que nos foi dado."</li></ul>
<dl><dd><dl>
  <dd>- <i>La sagesse consiste à ne pas détruire…</i></dd>   <!-- original -->
  <dd>- <i>Carnets - Volume 2, Gallimard, 1964, p. 86.</i></dd> <!-- fonte -->
</dl></dd></dl>
```

- Cada frase é um `<ul><li>"…"</li></ul>` **isolado** (um `li` por frase).
- A fonte/idioma original é o `<dl>` **irmão seguinte** (opcional; capturável
  como metadado).
- Seções são `<h2>`/`<h3>`/`<h4>` com `id` limpo.

### Algoritmo de extração (validado)

1. Pegar o container `//div[contains(@class,'mw-parser-output')]`.
2. Iterar os **filhos diretos em ordem**, mantendo a seção corrente:
   - filho que contém heading (`h2/h3/h4`) → atualiza `secao_atual` e decide
     `skip` pela **denylist**;
   - se `skip`, ignora até o próximo heading;
   - `<ul>` fora de seção-armadilha → cada `<li>` é uma frase.
3. Texto da frase = texto do `<li>` **excluindo sublistas** (`ul`/`dl` aninhados):
   `./text() | ./*[not(self::ul) and not(self::dl)]//text()`.
4. Normalizar espaços e remover aspas externas (`" “ ”`).
5. Descartar `len < 8` (ruído).

### Denylist de seções (não são frases DO autor)

`Sobre` · `Ligações externas` · `Ver também` · `Referências` · `Notas` ·
`Bibliografia` · `Fontes`

> **Armadilha crítica:** a seção **`Sobre`** contém frases ditas **por outros
> sobre** o autor. Incluí-la atribuiria a frase à pessoa errada. Nietzsche tem
> essa seção — confirmado que o algoritmo a exclui.

Normalizar o título antes de comparar: minúsculas + remover sufixo entre
parênteses (ex.: `O mito de sísifo (1942)` → base `o mito de sísifo`), porque a
denylist casa por título-base.

### Proveniência = a seção

O título da seção diz de onde vem a frase e vira metadado do `Quote`:
- **`Verificadas`** — frases com fonte confirmada (maior confiança).
- **Título de obra** (`Metafísica`, `A Peste`, …) — frase daquela obra.
- **`Atribuídas`** — atribuídas, sem fonte firme (menor confiança).

Sugestão de campo `Quote.categoria`: `verificada | obra | atribuida`, derivado
da seção (obra = qualquer seção não-denylist que não seja Verificadas/Atribuídas).

### Casos de borda observados

- Frases com aspas internas remanescentes (`…verdades absolutas".`) — a limpeza
  só tira aspas externas; deixar como está ou fazer trim simétrico.
- `(...)` no início é elipse legítima do original (Clarice) — **não** remover.
- Página sem headings (Sun Tzu) → frases caem em seção `(topo)`; tratar como
  `verificada`/genérica.

---

## Ponte nome → pensador → QID

Resolver o nome vago que o usuário digita e obter o **QID do Wikidata pela
própria página do Wikiquote** — assim bio (Wikidata) e frases (Wikiquote)
referem-se **garantidamente à mesma entidade**.

1. **Busca** (`list=search`, `srnamespace=0`) na Wikiquote PT. A **primeira
   hit** foi sempre a correta nos testes:
   `camus→Albert Camus`, `nietzsche→Friedrich Nietzsche`, `sun tzu→Sun Tzu`,
   `clarice→Clarice Lispector`, `platao→Platão`, `aristoteles→Aristóteles`.
2. **QID** da página escolhida via `prop=pageprops` → `pageprops.wikibase_item`
   (ex.: `Albert Camus → Q34670`). Usar `redirects=1` para seguir redirects.
3. Com o QID, buscar a bio no Wikidata (Pilar 2).

> Vantagem sobre buscar direto no Wikidata: o QID vem da mesma página das frases,
> eliminando ambiguidade (ex.: `Aristóteles` filósofo vs `Aristóteles Onassis`,
> que apareceu como 2ª hit).

Endpoints Wikiquote (todos `format=json&formatversion=2`, host
`pt.wikiquote.org/w/api.php`):

| Uso | Params |
|---|---|
| Buscar pensador | `action=query&list=search&srsearch=<q>&srnamespace=0&srlimit=5` |
| QID da página | `action=query&titles=<t>&prop=pageprops&redirects=1` |
| Frases (HTML) | `action=parse&page=<t>&prop=text` |
| Seções (debug) | `action=parse&page=<t>&prop=sections` |

---

## Pilar 2 — Perfil do Wikidata

### Decisão: REST `wbgetentities`, não SPARQL

Usar a **REST API** `www.wikidata.org/w/api.php?action=wbgetentities`, **não** o
SPARQL de `query.wikidata.org`.

**Por quê:** o SPARQL público é frágil como base de uma vitrine ao vivo. No
teste ele retornou o perfil completo do Camus, mas em seguida deu **HTTP 429**:
*"Aggressively rate-limiting to 1 req/min — this rule was created during active
wdqs outage"*. Uma demo não pode depender da saúde do WDQS. A `wbgetentities` é
**CDN-cacheada, estável e com limites folgados** (endpoint diferente, não afetado
pelo outage). Casa com o cache do ADR-005 e com as chamadas concorrentes do
ADR-004.

**Custo:** duas idas à rede (as duas cacheáveis):
1. `wbgetentities` do QID com `props=claims|descriptions|labels&languages=pt|en`.
2. Resolver os **labels das entidades referenciadas** (local, ocupação, obras…)
   num **batch** `wbgetentities` (até 50 QIDs por chamada, `props=labels`).

O SPARQL fica **documentado como alternativa** (uma query só, labels já
resolvidos) para quando 1 request bastar — ver query validada abaixo.

### Propriedades do perfil (fixadas)

| Prop | Campo | Multi? |
|---|---|---|
| `schema:description` (pt→en) | `descricao` | não |
| `P569` | `nascimento` (data) | pegar rank preferido |
| `P570` | `morte` (data) | idem |
| `P19` | `localNascimento` | 1 |
| `P20` | `localMorte` | 1 |
| `P27` | `nacionalidade` | N |
| `P106` | `ocupacoes` | N |
| `P135` | `correntes` (movimento) | N |
| `P69` | `formacao` (educação) | N |
| `P800` | `obras` (notáveis) | N |

Labels sempre com fallback **pt → en**; obras/entidade sem label em nenhum dos
dois → **descartar** (não vazar QID cru para o cliente).

### Casos de borda observados (obrigatório tratar)

- **Label ausente:** `Q120609061` (obra do Nietzsche) não tinha label pt/en e
  vazou como QID. → aplicar fallback de idioma e, se nada, omitir.
- **Datas AEC / parciais:** Sun Tzu `nascimento = -0544` (séc. VI a.C., mês/dia
  `00`). Truncar string quebra. → usar o campo **`precision`** do valor `time`
  do Wikidata (9 = ano, 11 = dia) e formatar conforme: "século V a.C.", "1913",
  "07/11/1913". Nunca assumir data completa.
- **Valores conflitantes:** Clarice tem 2 datas de nascimento (1920 e 1925); Sun
  Tzu 2 de morte. → preferir claims de **rank `preferred`**; senão, o 1º, e
  opcionalmente sinalizar incerteza.
- **Ocupações ruidosas:** Camus lista "futebolista" junto de "filósofo". Aceitar
  como está (é o dado real) — não filtrar arbitrariamente.

### Query SPARQL de referência (alternativa, validada com Camus)

```sparql
SELECT
 (SAMPLE(?nascData) AS ?nascimento) (SAMPLE(?morteData) AS ?morte)
 (SAMPLE(?nascLocalL) AS ?localNascimento) (SAMPLE(?descPt) AS ?descricao)
 (GROUP_CONCAT(DISTINCT ?ocupacaoL;separator=" | ") AS ?ocupacoes)
 (GROUP_CONCAT(DISTINCT ?correnteL;separator=" | ") AS ?correntes)
 (GROUP_CONCAT(DISTINCT ?formacaoL;separator=" | ") AS ?formacao)
 (GROUP_CONCAT(DISTINCT ?nacL;separator=" | ") AS ?nacionalidade)
 (GROUP_CONCAT(DISTINCT ?obraL;separator=" | ") AS ?obras)
WHERE {
 BIND(wd:Q34670 AS ?p)
 OPTIONAL { ?p wdt:P569 ?nascData. }
 OPTIONAL { ?p wdt:P570 ?morteData. }
 OPTIONAL { ?p wdt:P19 ?nascLocal. ?nascLocal rdfs:label ?nascLocalL. FILTER(LANG(?nascLocalL)="pt") }
 OPTIONAL { ?p wdt:P106 ?ocupacao. ?ocupacao rdfs:label ?ocupacaoL. FILTER(LANG(?ocupacaoL)="pt") }
 OPTIONAL { ?p wdt:P135 ?corrente. ?corrente rdfs:label ?correnteL. FILTER(LANG(?correnteL)="pt") }
 OPTIONAL { ?p wdt:P69 ?formacao. ?formacao rdfs:label ?formacaoL. FILTER(LANG(?formacaoL)="pt") }
 OPTIONAL { ?p wdt:P27 ?nac. ?nac rdfs:label ?nacL. FILTER(LANG(?nacL)="pt") }
 OPTIONAL { ?p wdt:P800 ?obra. ?obra rdfs:label ?obraL. FILTER(LANG(?obraL)="pt") }
 OPTIONAL { ?p schema:description ?descPt. FILTER(LANG(?descPt)="pt") }
} GROUP BY ?p
```

---

## Implicações para o modelo de dados

Com os pilares refinados, os campos ficam concretos:

```
Thinker:
  qid            str            # Q34670 (chave canônica)
  nome           str            # título Wikiquote / label Wikidata
  descricao      str | None     # 1 linha (schema:description pt→en)
  nascimento     DateParcial|N  # data + precisão (ano/dia/século)
  morte          DateParcial|N
  localNascimento str | None
  nacionalidade  list[str]
  ocupacoes      list[str]
  correntes      list[str]
  formacao       list[str]
  obras          list[Work]
  fontes         Attribution    # Wikidata (CC0) + Wikiquote (CC BY-SA)

Work:
  titulo  str
  qid     str | None

Quote:
  texto      str
  autor      str                # nome do Thinker
  categoria  Literal["verificada","obra","atribuida"]
  obra       str | None         # seção de origem, se for obra
  original   str | None         # idioma original (do <dl>), se houver
  fonte      Attribution        # Wikiquote CC BY-SA + URL da página
```

`DateParcial`: `{ valor: str ISO, precisao: "seculo|ano|mes|dia", exibicao: str }`.

---

## Estado dos pilares

- [x] **Parsing do Wikiquote** — HTML + lxml + denylist; validado (5 autores).
- [x] **Resolução nome → QID** — search + pageprops; validado.
- [x] **Query Wikidata** — REST `wbgetentities` (primária) + SPARQL (alternativa);
      validado; casos de borda mapeados.

Pré-requisitos de código atendidos. **Próximo passo real:** decidir o nome
(`NAMING.md`) e montar o esqueleto FastAPI em camadas (ADR-006) com dois clients
(`WikiquoteClient`, `WikidataClient`) implementando exatamente o descrito aqui.
