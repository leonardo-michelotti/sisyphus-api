# Decisões técnicas — API de Pensadores

Registro das decisões arquiteturais e **por que** cada uma foi escolhida.
Enquanto o projeto está em planejamento, os ADRs ficam com status `proposto`.
Cada entrada segue o modelo abaixo.

<!--
## ADR-NNN: <título curto da decisão>

**Status:** proposto | aceito | substituído pelo ADR-XXX

### Contexto
Qual problema/força motivou a decisão?

### Decisão
O que foi decidido, em uma frase objetiva.

### Alternativas consideradas
- Opção A — por que não.

### Motivos
Por que esta opção venceu.

### Trade-offs e consequências
O que essa escolha custa / o que passa a ser obrigatório.
-->

## Resumo

Por que escolhemos o que escolhemos, em uma linha cada.

| ADR | Escolha | Por quê, em uma linha |
|---|---|---|
| 001 | Fontes abertas (Wikiquote + Wikidata) em vez de scraping do Pensador | O Pensador bloqueia robôs (Cloudflare); fontes estruturadas são legais, confiáveis e dispensam navegador. |
| 002 | FastAPI como framework | Padrão atual de API Python: async, OpenAPI automático, tipagem — a vitrine que o projeto quer ser. |
| 003 | Pydantic v2 para modelos e validação | Contratos tipados que geram o schema OpenAPI e validam entrada/saída sem código manual. |
| 004 | httpx async com chamadas concorrentes | Frases e biografia vêm de fontes diferentes; buscar em paralelo reduz a latência. |
| 005 | Cache com TTL | Frases e biografia mudam pouco; cache evita bater nas fontes a cada request. |
| 006 | Estrutura em camadas (routers/services/clients/schemas) | Separar HTTP, orquestração e acesso a fontes; hoje tudo vive em dois arquivos. |
| 007 | Semântica HTTP e erros tipados | Distinguir "pensador não encontrado" (404) de "fonte fora" (502/504); hoje erro vira `[]` com 200. |
| 008 | Config via pydantic-settings + `.env` | Sem segredos/flags no código; `debug=True` fixo é risco. |
| 009 | Empacotamento moderno (`pyproject.toml`) | Padrão atual de projeto Python; `requirements.txt` solto não declara o projeto. |
| 010 | Qualidade: ruff + mypy + pytest | Lint, formatação, tipos e testes são o que uma vitrine precisa mostrar. |
| 011 | Docker + docker-compose | Paridade dev/prod e execução reproduzível em um comando. |
| 012 | CI com GitHub Actions | Lint + tipos + testes verdes a cada push, visíveis no repositório. |
| 013 | Deploy com demo ao vivo + Swagger público | Uma URL navegável vale mais que um README num portfólio. |
| 014 | Rate limiting leve + CORS | Público, mas protegido contra abuso e utilizável por front-ends. |
| 015 | Atribuição Wikimedia (CC BY-SA) | O conteúdo é de terceiros sob licença que exige crédito. |
| 016 | Parsing do Wikiquote via HTML renderizado + lxml (não regex em wikitext) | O MediaWiki já expande templates e resolve wikilinks; o HTML é uniforme entre autores (validado em 5). |
| 017 | Bio via REST `wbgetentities`, não SPARQL | O SPARQL público é frágil (429 por outage no teste); a REST é CDN-cacheada e estável — melhor para uma demo ao vivo. |
| 018 | Nome→QID pela página do Wikiquote (`search` + `pageprops`) | O QID vem da mesma página das frases, garantindo que bio e frases são a mesma entidade e evitando desambiguação. |
| 019 | Versionamento por URI (`/v1`) | API pública precisa evoluir sem quebrar clientes; URI é o esquema mais visível e simples para isso. |
| 020 | Envelope `{data, meta}` em coleções + paginação | Resposta consistente e paginável em toda a API, em vez de arrays crus que não carregam metadados. |
| 021 | Cache HTTP (ETag/Cache-Control + conditional GET) | O conteúdo é ~imutável; ETag corta transferência e mostra domínio de semântica HTTP numa demo ao vivo. |
| 022 | Observabilidade: log estruturado (JSON) + request-id + `/health` que checa upstream | Log texto não rastreia; correlação por request-id e health real são o mínimo de operação séria. |
| 023 | Busca semântica: embeddings locais + sqlite-vec + corpus semente | Busca por significado é o diferencial de ML; modelo local e índice embutido mantêm grátis, self-contained e sem infra extra. |
| 024 | Grafo de influências via Wikidata P737 | Explora a natureza-grafo do Wikidata para linhagem intelectual — distinção visual que "sai da lista de frases". |
| 025 | Servidor MCP expondo as capacidades como tools | Torna o sisyphus consumível por agentes de IA/Claude — diferencial 2026 que amarra a tese do produto. |
| 026 | Frase-do-dia determinística + página-demo | Ataca o fator nº1 de portfólio (app rodando + 1ª impressão) com baixo esforço. |
| 027 | Imagem de runtime imutável com SQLite curado | Une código e dataset validados no mesmo digest, sem carregar o pipeline em produção. |

> Novos ADRs (019–026) estão como `proposto` e detalhados sob demanda ao iniciar
> cada fase (ver `ROADMAP.md`). Os campos completos (contexto/alternativas/
> trade-offs) são preenchidos no momento da implementação.

---

## Arquitetura-alvo (proposta)

```text
                 Cliente HTTP
                      │  JSON
                      ▼
              ┌───────────────┐
              │  FastAPI      │  routers (HTTP fino) + OpenAPI/Swagger
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │  Services     │  orquestra: monta o perfil do pensador
              └───┬───────┬───┘
                  │       │        chamadas concorrentes (httpx async)
        ┌─────────▼──┐ ┌──▼──────────┐
        │ Wikidata   │ │ Wikiquote   │  clients (um por fonte)
        │ (SPARQL)   │ │ (MediaWiki) │
        └─────────┬──┘ └──┬──────────┘
                  └───┬───┘
                      ▼
                 ┌─────────┐
                 │  Cache  │  TTL (frases/bio mudam pouco)
                 └─────────┘
```

**Endpoints propostos:**

| Método | Rota | Retorna |
|---|---|---|
| GET | `/thinkers/{nome}` | Perfil: bio + obras + amostra de frases |
| GET | `/thinkers/{nome}/quotes` | Frases paginadas (Wikiquote) |
| GET | `/search?q=` | Busca de pensadores por nome |
| GET | `/health` | Healthcheck |

**Modelos (Pydantic):** `Thinker` (nome, nascimento, local, ocupação, corrente,
período), `Work` (obra), `Quote` (texto, autor, fonte).

---

## ADR-001: Fontes abertas estruturadas em vez de scraping do Pensador

**Status:** proposto — **decisão central; base de todo o resto**

### Contexto
O projeto original raspava `pensador.com` com Selenium. Ao verificar a fonte:
uma requisição com cabeçalho de navegador completo recebe **HTTP 403** e a tela
`"Just a moment..."` do **Cloudflare** (`challenge-platform`). O site bloqueia
ativamente qualquer acesso que não seja um navegador real executando JavaScript.

Além disso, a visão de produto cresceu: não só frases, mas **obras e
biografia** (onde nasceu, onde estudou, corrente), que o Pensador nem oferece.

### Decisão
Abandonar o scraping do Pensador. Usar **Wikiquote** (`pt.wikiquote.org`, API
MediaWiki) para frases em português e **Wikidata** (SPARQL) para dados
biográficos e obras.

### Alternativas consideradas
- **Scraping do Pensador via navegador headless (Selenium/Playwright)** — única
  forma de passar pelo Cloudflare, mas pesado, frágil, contra a vontade
  explícita do site e ruim como vitrine.
- **Scraping do Pensador via `requests`/`httpx`** — inviável: bloqueado pelo
  Cloudflare (403 confirmado).

### Motivos
- Wikiquote e Wikidata são **abertas, legais e estruturadas**, sem navegador.
- Cobrem a visão completa (frases + obras + biografia), o que o Pensador não faz.
- **Validado com dados reais:** Wikiquote devolveu frases do Aristóteles em PT;
  Wikidata devolveu nascimento (Estagira), ocupação, corrente e obras.

### Trade-offs e consequências
- A **identidade muda**: deixa de ser "raspador do Pensador" e vira "API de
  pensadores". O nome do repositório pode ser revisto.
- Depende da **cobertura** do Wikiquote/Wikidata: autores populares têm dados
  ricos; obscuros podem ter pouco ou nada.
- Passa a existir dependência de disponibilidade das APIs Wikimedia (mitigada
  por cache — ADR-005) e obrigação de atribuição (ADR-015).

---

## ADR-002: FastAPI como framework HTTP

**Status:** proposto

### Contexto
O projeto atual usa Flask com o servidor de desenvolvimento. Como vitrine,
precisa refletir o padrão atual de APIs em Python.

### Decisão
Reescrever a API em **FastAPI**.

### Alternativas consideradas
- **Flask (atual)** — maduro, mas síncrono por padrão, sem validação/schema
  nativos e sem documentação automática.
- **Django REST Framework** — completo demais; traz ORM e estrutura pesada
  desnecessária para um serviço de leitura sobre APIs externas.

### Motivos
- **Async nativo**, ideal para um serviço que é I/O-bound (chama Wikiquote e
  Wikidata) — ver ADR-004.
- **OpenAPI/Swagger gerado automaticamente** a partir dos tipos — documentação
  viva sem esforço, ótima para portfólio.
- Integração nativa com **Pydantic** (ADR-003) para validação e schema.

### Trade-offs e consequências
- Exige Python 3.10+ e disciplina com async (não bloquear o event loop).

---

## ADR-003: Pydantic v2 para modelos, validação e schema

**Status:** proposto

### Contexto
As respostas têm forma bem definida (pensador, obra, frase) e a entrada precisa
ser validada (nome, paginação).

### Decisão
Modelar entrada e saída com **Pydantic v2**, aproveitando a integração do
FastAPI.

### Alternativas consideradas
- **dataclasses / dicts manuais** — sem validação nem geração de schema; mais
  código e mais erro.

### Motivos
- Um único modelo tipado serve de validação, serialização e **fonte do schema
  OpenAPI**.
- Deixa explícito o contrato da API — parte central do que a vitrine demonstra.

### Trade-offs e consequências
- Modelos precisam ser mantidos em sincronia com o formato real das fontes.

---

## ADR-004: httpx async com chamadas concorrentes às fontes

**Status:** proposto

### Contexto
Montar o perfil de um pensador exige buscar em **duas fontes distintas**
(Wikiquote e Wikidata). Em série, a latência é a soma das duas.

### Decisão
Usar **httpx** (cliente async) e disparar as chamadas às fontes de forma
**concorrente** (`asyncio.gather`).

### Alternativas consideradas
- **requests (síncrono, atual)** — bloqueante; forçaria as chamadas em série ou
  o uso de threads.

### Motivos
- Casa com o FastAPI async (ADR-002).
- Buscar frases e biografia em paralelo reduz a latência ao tempo da fonte mais
  lenta, não à soma.

### Trade-offs e consequências
- Código async exige cuidado com timeouts e tratamento de falha por fonte
  (uma fonte pode responder e a outra falhar — ver ADR-007).

---

## ADR-005: Cache com TTL

**Status:** proposto

### Contexto
Frases e biografia de um pensador mudam muito raramente, mas cada request bateria
nas APIs Wikimedia — mais lento e sem necessidade.

### Decisão
Cachear as respostas das fontes por chave (pensador) com **TTL**. Começar com
cache **em memória** (ex.: TTL cache); Redis fica como evolução se houver
múltiplas réplicas.

### Alternativas consideradas
- **Sem cache** — simples, mas lento e desnecessariamente pesado sobre as fontes
  de terceiros (e deselegante para um serviço de leitura).
- **Redis desde o início** — infra extra sem ganho enquanto for réplica única.

### Motivos
- Dados quase estáticos: cache tem alta taxa de acerto.
- Reduz latência e uso das APIs Wikimedia (boa cidadania).

### Trade-offs e consequências
- Cache em memória não é compartilhado entre réplicas; escalar horizontalmente
  exigiria Redis (revisitar esta decisão).

---

## ADR-006: Estrutura em camadas (routers / services / clients / schemas)

**Status:** proposto

### Contexto
Hoje tudo vive em `app.py` (rota) e `scraper.py` (acesso), sem separação de
responsabilidades.

### Decisão
Separar em camadas: **routers** (HTTP fino) → **services** (orquestra o perfil)
→ **clients** (um por fonte: `WikiquoteClient`, `WikidataClient`) → **schemas**
(modelos Pydantic).

### Alternativas consideradas
- **Tudo em um arquivo (atual)** — rápido de começar, difícil de testar e
  evoluir; a rota conhece detalhes de scraping.

### Motivos
- Cada camada é testável isoladamente (ex.: mockar clients nos testes).
- Trocar/adicionar uma fonte fica contido em um client.

### Trade-offs e consequências
- Mais arquivos e cerimônia inicial — justificável pelo objetivo de vitrine.

---

## ADR-007: Semântica HTTP e erros tipados

**Status:** proposto

### Contexto
Hoje o timeout retorna `[]` com **HTTP 200**, e "autor não existe" é
indistinguível de "deu erro". Um cliente não consegue reagir corretamente.

### Decisão
Mapear estados em status HTTP claros: **200** com dados; **404** pensador não
encontrado; **502/504** quando uma fonte upstream falha ou expira; corpo de erro
consistente (formato tipo `problem+json`).

### Alternativas consideradas
- **Sempre 200 com lista vazia (atual)** — esconde a diferença entre "não há" e
  "falhou", impossibilita cache/retry corretos no cliente.

### Motivos
- Semântica HTTP correta é o básico esperado de uma API de referência.
- Permite ao cliente distinguir ausência de dados de falha temporária.

### Trade-offs e consequências
- Exige tratar falha por fonte (perfil pode vir parcial: bio ok, frases fora).

---

## ADR-008: Configuração via pydantic-settings e `.env`

**Status:** proposto

### Contexto
O projeto atual roda com `app.run(debug=True)` — flag de debug fixa no código,
que em produção expõe o debugger do Werkzeug (RCE).

### Decisão
Externalizar configuração (timeouts, TTL de cache, endpoints das fontes, host/
porta, nível de log) via **pydantic-settings** lendo variáveis de ambiente/`.env`.
Debug desligado por padrão.

### Alternativas consideradas
- **Constantes no código (atual)** — inflexível e inseguro.

### Motivos
- Configuração tipada e validada, sem segredos/flags no código.
- Diferencia ambientes (dev/prod) sem editar código.

### Trade-offs e consequências
- Requer documentar as variáveis (README) e valores padrão sensatos.

---

## ADR-009: Empacotamento moderno com `pyproject.toml`

**Status:** proposto

### Contexto
Hoje há apenas um `requirements.txt` com três linhas, sem metadados de projeto.

### Decisão
Declarar o projeto em **`pyproject.toml`** (dependências, versão de Python,
config de ruff/mypy/pytest num só lugar). Instalação reproduzível (pip/uv).

### Alternativas consideradas
- **`requirements.txt` solto (atual)** — não descreve o projeto nem centraliza a
  config das ferramentas.

### Motivos
- Padrão atual de empacotamento Python (PEP 621).
- Um único arquivo concentra dependências e configuração de qualidade.

### Trade-offs e consequências
- Nenhum relevante; é o caminho recomendado hoje.

---

## ADR-010: Qualidade — ruff, mypy e pytest

**Status:** proposto

### Contexto
O projeto não tem lint, checagem de tipos nem testes. Numa vitrine, isso é
justamente o que se quer demonstrar.

### Decisão
Adotar **ruff** (lint + formatação), **mypy** (tipos) e **pytest** (testes, com
clients mockados). Opcional: **pre-commit** para rodar tudo antes do commit.

### Alternativas consideradas
- **black + flake8 + isort separados** — ruff faz os três, mais rápido e num só
  config.
- **Sem testes/tipos** — inaceitável para o objetivo de portfólio.

### Motivos
- Demonstra rigor de engenharia; ruff é o padrão atual e consolidado.
- Testes com clients mockados isolam a lógica das fontes externas.

### Trade-offs e consequências
- Custo de manter os checks verdes — que é exatamente o valor a mostrar.

---

## ADR-011: Docker e docker-compose

**Status:** proposto

### Contexto
Precisa rodar de forma reproduzível em qualquer máquina e no deploy.

### Decisão
Fornecer **Dockerfile** (imagem enxuta, servidor ASGI como uvicorn/gunicorn) e
**docker-compose** para subir o serviço (e Redis, se/quando adotado) num comando.

### Alternativas consideradas
- **Só instruções de venv no README** — funciona, mas não garante paridade
  dev/prod nem impressiona numa vitrine.

### Motivos
- Paridade dev/prod e "clone e `docker compose up`".
- Base pronta para o deploy (ADR-013).

### Trade-offs e consequências
- Manter a imagem enxuta e atualizada.

---

## ADR-012: CI com GitHub Actions

**Status:** proposto

### Contexto
Sendo público, o repositório ganha muito com sinais visíveis de qualidade.

### Decisão
Pipeline no **GitHub Actions** rodando ruff, mypy e pytest a cada push/PR, com
badge de status no README.

### Alternativas consideradas
- **Sem CI** — perde o sinal de qualidade e permite regressões silenciosas.

### Motivos
- Verde a cada push é a prova pública de que os checks do ADR-010 valem.

### Trade-offs e consequências
- Manter o workflow; tempo de CI (pequeno neste escopo).

---

## ADR-013: Deploy com demo ao vivo e Swagger público

**Status:** proposto

### Contexto
Num portfólio, uma URL navegável vale mais que qualquer descrição.

### Decisão
Publicar em uma plataforma simples (Railway/Fly/Render) expondo o **Swagger UI**
público (gerado pelo FastAPI), com link no README.

### Alternativas consideradas
- **Só rodar local** — reduz o impacto de vitrine.

### Motivos
- Deixa qualquer pessoa experimentar a API sem instalar nada.
- Aproveita o OpenAPI automático do FastAPI (ADR-002).

### Trade-offs e consequências
- Custo/limites de plano gratuito; expõe a API a tráfego externo (mitigado pelo
  ADR-014).

---

## ADR-014: Rate limiting leve e CORS

**Status:** proposto

### Contexto
A API é pública, mas não se destina a uso massivo; ainda assim precisa ser
utilizável por front-ends e protegida contra abuso.

### Decisão
Aplicar **rate limiting** por IP (limites folgados) e **CORS** configurável.

### Alternativas consideradas
- **Sem limites** — expõe o serviço (e as fontes Wikimedia atrás dele) a abuso.

### Motivos
- Protege o serviço e as fontes de terceiros; boa cidadania.
- CORS permite consumo direto de um front-end de demonstração.

### Trade-offs e consequências
- Ajustar limites para não atrapalhar uso legítimo/demonstração.

---

## ADR-015: Atribuição do conteúdo Wikimedia (CC BY-SA)

**Status:** proposto

### Contexto
Frases (Wikiquote) e dados (Wikidata/Wikipedia) são conteúdo de terceiros sob
licenças Wikimedia — Wikiquote é **CC BY-SA**; Wikidata é **CC0**.

### Decisão
**Atribuir** a fonte em cada resposta e na documentação (link para a página de
origem e menção à licença), respeitando os termos.

### Alternativas consideradas
- **Não creditar** — viola a licença CC BY-SA do Wikiquote.

### Motivos
- Obrigação legal e ética ao redistribuir conteúdo CC BY-SA.
- Transparência sobre a origem dos dados valoriza a API.

### Trade-offs e consequências
- Cada resposta carrega metadados de fonte/licença — custo mínimo, benefício de
  conformidade.

---

## ADR-016: Parsing do Wikiquote via HTML renderizado + lxml

**Status:** proposto — **validado em 5 autores (ver `PILARES_TECNICOS.md`)**

### Contexto
As frases do Wikiquote não têm API estruturada; vêm no corpo da página. A opção
óbvia (`prop=wikitext`) entrega markup cru: templates, wikilinks `[[a|b]]`,
formatação — que varia por página e é frágil de tratar por regex.

### Decisão
Buscar o **HTML renderizado** (`action=parse&prop=text`) e extrair as frases
percorrendo o DOM com **lxml**: iterar os filhos de `.mw-parser-output`,
rastrear a seção corrente, e coletar cada `<ul><li>` como uma frase, pulando
seções da **denylist** (`Sobre`, `Ligações externas`, `Ver também`,
`Referências`, `Notas`, `Bibliografia`, `Fontes`).

### Alternativas consideradas
- **Regex sobre `wikitext`** — teria que reimplementar expansão de template e
  resolução de wikilink; quebra entre páginas.
- **Biblioteca de parsing de wikitext (mwparserfromhell)** — resolve o markup,
  mas ainda não separa frase de fonte nem trata seções; o HTML já vem pronto.

### Motivos
- O MediaWiki já expandiu templates e resolveu wikilinks (`[[amor|amar]]` →
  texto `amar`); o HTML é uniforme entre autores (confirmado em 5 perfis).
- Cada frase é um `<ul><li>` isolado e a fonte é o `<dl>` irmão — estrutura
  estável e fácil de mapear.

### Trade-offs e consequências
- Depende da estabilidade do HTML do MediaWiki (baixa rotatividade) e de manter
  a denylist. Adiciona `lxml` como dependência.
- A seção de origem vira proveniência da frase (`verificada|obra|atribuida`).
- **Armadilha coberta:** a seção `Sobre` (frases de terceiros sobre o autor) é
  excluída para não gerar atribuição errada.

---

## ADR-017: Biografia via REST `wbgetentities`, não SPARQL

**Status:** proposto — **validado (SPARQL deu 429 em teste real)**

### Contexto
O perfil biográfico vem do Wikidata. Há dois caminhos: o endpoint **SPARQL**
(`query.wikidata.org`, uma query devolve tudo com labels) e a **REST API**
(`www.wikidata.org/w/api.php?action=wbgetentities`, claims cruas + labels em
chamada à parte).

### Decisão
Usar a **REST `wbgetentities`** como fonte primária: (1) buscar o QID com
`props=claims|descriptions|labels&languages=pt|en`; (2) resolver os labels das
entidades referenciadas num **batch** (até 50 QIDs, `props=labels`). Manter o
SPARQL apenas como alternativa documentada.

### Alternativas consideradas
- **SPARQL** — elegante (uma query, labels já resolvidos, filtragem exata das
  props). Mas no teste retornou **HTTP 429**: *"Aggressively rate-limiting to
  1 req/min — active wdqs outage"*. Frágil como base de uma demo ao vivo.

### Motivos
- A REST é **CDN-cacheada, estável e com limites folgados** — endpoint distinto,
  não afetado por outage do WDQS.
- Casa com o cache (ADR-005) e com as chamadas concorrentes (ADR-004): as duas
  idas à rede são cacheáveis.

### Trade-offs e consequências
- Custo de **duas chamadas** e de resolver labels manualmente (a SPARQL faria em
  uma). Aceitável dado o ganho de robustez.
- Exige tratar casos de borda das claims cruas: datas AEC/parciais (usar
  `precision`), label ausente (fallback pt→en, senão omitir), valores
  conflitantes (preferir rank `preferred`).

---

## ADR-018: Resolução nome→QID pela página do Wikiquote

**Status:** proposto — **validado**

### Contexto
O usuário digita um nome vago ("camus", "clarice"). Precisamos (a) achar o
pensador certo e (b) obter seu QID para a bio — sem misturar entidades
homônimas.

### Decisão
Resolver **na Wikiquote**: `list=search` (namespace 0) devolve a página; a 1ª
hit foi sempre correta nos testes. O QID vem de `prop=pageprops` →
`pageprops.wikibase_item` **da mesma página** que fornece as frases.

### Alternativas consideradas
- **Buscar direto no Wikidata (`wbsearchentities`)** — resolveria o QID, mas por
  fora do Wikiquote; arrisca escolher uma entidade cujo QID não tem página de
  frases, e exige desambiguar homônimos (ex.: `Aristóteles` filósofo vs
  `Aristóteles Onassis`).

### Motivos
- O QID vindo da página das frases **garante que bio e frases são a mesma
  entidade**.
- Uma busca textual simples cobre a entrada vaga do usuário; `redirects=1` trata
  variações de título.

### Trade-offs e consequências
- Depende da existência de página no Wikiquote PT (sem página → sem frases, o que
  já é o comportamento desejado). Homônimos raros podem exigir refinar a escolha
  da hit no futuro.

---

## ADR-027: Imagem imutável une aplicação e dataset curado

**Status:** aceito

### Contexto

A frase do dia passa a depender de um SQLite gerado fora do runtime. O arquivo não
deve entrar no Git, e construir o pipeline durante cada deploy introduziria rede,
dbt e dados mutáveis no caminho crítico da publicação.

### Decisão

Gerar o SQLite em um workflow manual, validá-lo e construir uma imagem de runtime
que contenha a aplicação e exatamente aquele banco. Publicar no GHCR somente com
confirmação explícita, usando tag imutável, digest OCI e atestação de procedência.

### Alternativas consideradas

- **Construir durante o deploy no Railway:** mistura coleta e runtime, aumenta o
  tempo de build e pode publicar resultados diferentes a partir do mesmo commit.
- **Baixar um SQLite no início do contêiner:** cria uma dependência externa em cada
  inicialização e permite divergência entre código e dataset.
- **Versionar o SQLite no Git:** aumenta o repositório com um binário derivado e
  enfraquece a separação entre fonte, regras e artefato.

### Motivos

- O digest identifica código, dependências e dados como uma unidade.
- O runtime permanece pequeno e não carrega DuckDB, dbt ou credenciais de coleta.
- O Railway pode retornar a uma imagem anterior sem reconstruir o dataset.
- A publicação manual corresponde ao volume e à maturidade atual do produto.

### Trade-offs e consequências

- Uma nova base exige uma nova imagem.
- A visibilidade do pacote e o plano do Railway precisam ser decididos antes do
  primeiro deploy.
- Tags não podem ser sobrescritas pelo processo normal de publicação.
- A última tag e o digest aprovados devem permanecer registrados fora da retenção
  operacional do Railway.
