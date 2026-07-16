# Roadmap — de esqueleto a vitrine

**Objetivo atual:** validar o uso das coleções e do widget antes de ampliar o
corpus ou adicionar uma nova camada técnica. O diagnóstico inicial de que o projeto
era apenas um proxy já foi superado pela base curada, pela vitrine e pela publicação.
Este documento preserva a **tese de produto** e a **sequência de execução** decidida
em 2026-07-05.

Ler junto com `PRODUCT_VISION.md` (o quê/por quê) e `DECISIONS.md` (ADRs).

## Tese

> **sisyphus** — API aberta para explorar pensadores: suas ideias, frases e
> **redes de influência**, pesquisáveis **por significado**, consumíveis por
> **humanos** (site-demo), **máquinas** (REST) e **agentes de IA** (MCP).

Deixa de ser "wrapper de Wikiquote" e passa a ter tese própria. O que faz o repo
parar o scroll não é o código limpo (ninguém audita na primeira olhada) e sim
**produto distinto + vitrine viva + sinais de senioridade**.

## Dois eixos de melhoria

**Eixo A — maturidade de engenharia**. A tabela registra o ponto de partida
mapeado em 2026-07-05; os itens foram concluídos na Fase 0:

| Padrão | Estado hoje | Ação | Fonte |
|---|---|---|---|
| Problem details **RFC 9457** (sucessor do 7807) | tem problem+json | citar RFC 9457, add `type` URI + `instance` | [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) |
| Versionamento por URI (`/v1`) p/ API pública | sem versão | prefixo `/v1` | [Azure API Design](https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design) |
| Envelope `{data, meta}` em coleções | array cru | envelope paginável | [Fern 2026](https://buildwithfern.com/post/api-design-best-practices-guide) |
| Paginação cursor-based (offset saindo) | offset/limit | cursor opaco _ou_ offset assumido (corpus pequeno) | idem |
| **RateLimit headers** (anunciar quota, não só bloquear) | ausente | `RateLimit-Policy`/`RateLimit` + 429 | [IETF draft-11](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/) |
| Cache HTTP (ETag/Cache-Control/conditional) | só cache interno | ETag — upstream é ~imutável | idem |
| Observabilidade (log estruturado, request-id, `/health` que checa upstream) | log texto | JSON logs + request-id | — |

**Eixo B — distinção de produto** (faz parar o scroll). Compliance com RFC não dá
brilho sozinha; um proxy RFC-perfeito continua entediante. Os quatro diferenciais
escolhidos estão nas fases 1–4 abaixo.

## Sequência de execução

Ordem escolhida por **dependência e peso** — nada brilha antes de estar no ar e
parecendo profissional; o "wow" de ML vem depois da base sólida.

### Fase 0 · Fundação senior + deploy
Deixar a API atual nível-senior e **no ar**.
- `/v1` + envelope `{data, meta}`; RFC 9457 (`type`/`instance`).
- RateLimit headers + 429; ETag/Cache-Control.
- Log estruturado (JSON) + request-id; `/health` que checa upstream.
- Docker + docker-compose; CI (ruff/mypy/pytest + coverage badge).
- Testes de client com `respx` (rede/erros, hoje só funções puras).
- **Deploy no Railway** com Swagger público.
- ADRs: 011, 012, 013, 014 (já propostos) + 019–022 (novos).

**Estado:** concluída. A API está versionada, observável, testada e publicada com
cache, limites explícitos, respostas RFC 9457 e runtime sem privilégios.

### Fase 1 · Vitrine viva
O brilho visível, baixo esforço.
- `GET /v1/quote-of-the-day` — determinístico por data (seed curado).
- **Página-demo** bonita consumindo a API ao vivo (busca → perfil → frase do dia).
- README repaginado: hero, badges, diagrama de arquitetura, gif da demo, links vivos.
- ADRs: 026.

**Estado:** concluída. A frase diária usa o SQLite curado, o widget e a vitrine
consomem a mesma regra, e a imagem imutável com a base validada está publicada no
Railway. A interface oferece gerador, dez coleções editoriais e documentação de uso.

### Fase 2 · Grafo de influências
Usa a natureza-grafo do Wikidata que já consultamos.
- `GET /v1/thinkers/{nome}/influences` — Wikidata **P737** (influenciado por).
- Viz force-graph da linhagem intelectual na demo.
- ADRs: 024.

**Estado:** primeira fatia implementada. O endpoint e a visualização acessível cobrem
relações diretas. Expansão recursiva e force layout ficam condicionados à utilidade
observada, para evitar custo upstream e complexidade visual sem demanda comprovada.

### Próxima entrega · Coleções verificáveis

- auditoria reproduzível da cobertura diária por coleção;
- página própria com descrição, pensadores e amostra curada;
- teste real de incorporação antes de ampliar o corpus;
- correção de lacunas editoriais orientada pelo relatório, não por volume bruto.

### Fase 3 · Busca semântica
O "wow" ML — o mais pesado, por isso depois da base.
- Pipeline: ingestão de corpus semente (~50–100 pensadores canônicos) →
  embeddings → índice vetorial.
- `GET /v1/quotes/search?q=...&mode=semantic` — frases por significado.
- **Decisões a fechar ao iniciar:** modelo de embedding **local** multilíngue
  (sentence-transformers) para manter grátis/self-contained; **sqlite-vec** como
  índice (zero infra extra, cabe no container Railway); escopo do corpus e
  estratégia de refresh.
- ADRs: 023.

### Fase 4 · Servidor MCP
Por último de propósito — as tools ficam ricas porque as features já existem.
- Expõe `search_thinkers`, `get_profile`, `semantic_search`, `influences`,
  `quote_of_the_day` como tools MCP.
- Seção no README: "Use com Claude / agentes".
- ADRs: 025.

## Fora de escopo (por ora)
- Escrita/CRUD — o sisyphus é read-only sobre fontes abertas.
- Autenticação de usuários — API pública; proteção é rate limit + CORS (ADR-014).
- Alta escala — a meta é vitrine, não throughput (ver `PRODUCT_VISION.md`).
</content>
</invoke>
