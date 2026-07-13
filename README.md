# sisyphus

API pública e widget incorporável para descobrir frases de filósofos,
sociólogos, escritores e cientistas com autoria, contexto e fonte identificada.
O projeto combina Wikiquote e Wikidata por meio das APIs Wikimedia, sem
automação de navegador.

[Experimentar](https://sisyphus-public-production.up.railway.app/) ·
[Swagger](https://sisyphus-public-production.up.railway.app/docs) ·
[Mapa de influências](https://sisyphus-public-production.up.railway.app/influences?thinker=Albert%20Camus)

## O produto

O Sisyphus oferece três formas de explorar o mesmo conteúdo:

- **widget:** uma URL pronta para Notion, Obsidian e sites;
- **API REST:** perfis, frases, coleções e seleção diária ou aleatória;
- **mapa de influências:** relações intelectuais diretas registradas no Wikidata.

A frase diária é determinística durante a data UTC. A seleção aleatória não é
armazenada em cache. As coleções organizam personalidades por recortes
editoriais; a curadoria individual de frases ainda é uma evolução planejada.

## Teste rápido

```bash
curl "https://sisyphus-public-production.up.railway.app/v1/quote-of-the-day"
```

```json
{
  "frase": {
    "texto": "...",
    "autor": "Albert Camus",
    "categoria": "verificada",
    "fonte": {
      "fonte": "Wikiquote",
      "licenca": "CC BY-SA 4.0"
    }
  },
  "modo": "daily",
  "data": "2026-07-12"
}
```

O conteúdo varia conforme a data e os filtros. O contrato completo está no
[OpenAPI público](https://sisyphus-public-production.up.railway.app/docs).

## Arquitetura

```text
Cliente
  └─ FastAPI
       ├─ Wikiquote → resolução de nome e frases
       ├─ Wikidata  → biografia, obras e influências P737
       └─ serviços  → seleção, filtros, atribuição e cache
            ├─ REST JSON
            ├─ widget HTML
            └─ mapa de influências
```

O nome informado é resolvido primeiro pela página do Wikiquote. O QID associado
a essa página identifica a mesma pessoa no Wikidata, reduzindo o risco de
combinar entidades homônimas. Biografia e frases são consultadas de forma
concorrente, com cache interno e validação dos contratos na borda.

Decisões, alternativas e limites estão registrados em
[`docs/DECISIONS.md`](docs/DECISIONS.md) e
[`docs/PILARES_TECNICOS.md`](docs/PILARES_TECNICOS.md).

## Endpoints

| Método | Rota | Retorna |
|---|---|---|
| `GET` | `/v1/thinkers/{nome}` | Perfil, obras e amostra de frases |
| `GET` | `/v1/thinkers/{nome}/quotes` | Frases paginadas |
| `GET` | `/v1/thinkers/{nome}/influences` | Influências diretas via Wikidata P737 |
| `GET` | `/v1/search?q=` | Busca de personalidades por nome |
| `GET` | `/v1/quotes/random` | Frase aleatória com filtros |
| `GET` | `/v1/quote-of-the-day` | Frase diária determinística em UTC |
| `GET` | `/v1/collections` | Coleções editoriais de personalidades |
| `GET` | `/widget` | Widget incorporável |
| `GET` | `/influences` | Mapa visual de influências |
| `GET` | `/health` | Estado do serviço |

Listas usam o envelope `{data, meta}`. Erros seguem RFC 9457 em
`application/problem+json`. As respostas também expõem ETag, cache HTTP,
request ID e headers de rate limit quando aplicável.

## Incorporando o widget

Configure coleção e ritmo na [página inicial](https://sisyphus-public-production.up.railway.app/)
ou monte a URL diretamente:

```text
https://sisyphus-public-production.up.railway.app/widget?collection=existencia-e-absurdo&mode=daily
```

No Notion, cole a URL e escolha a opção de incorporação. Em uma nota do Obsidian
com suporte a HTML incorporado:

```html
<iframe
  src="https://sisyphus-public-production.up.railway.app/widget?mode=daily"
  width="100%"
  height="320"
  title="Frase do dia"
></iframe>
```

Parâmetros disponíveis: `collection`, `thinker`, `mode` (`daily` ou `random`)
e `show_context`.

## Desenvolvimento local

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn sisyphus.main:app --reload
```

Configure no `.env` um `User-Agent` com contato válido para as APIs Wikimedia.
Depois, abra `http://localhost:8000/docs`.

## Qualidade

```bash
ruff format --check .
ruff check .
mypy
pytest
```

Os testes usam fixtures locais e clients HTTP simulados. O CI executa Python
3.10 e 3.12, análise estática, tipagem estrita, testes e auditoria de
dependências.

## Limites atuais

- as frases dependem da estrutura e da disponibilidade do Wikiquote em português;
- o mapa mostra apenas relações P737 declaradas, não toda a história intelectual;
- as coleções curam grupos de personalidades, ainda não cada frase individual;
- o produto é somente leitura e não possui contas ou painel administrativo.

## Evolução

Os próximos experimentos e os critérios usados para priorizá-los estão no
[roadmap](docs/ROADMAP.md).

## Fontes e licença

O conteúdo do Wikiquote é atribuído sob CC BY-SA e o Wikidata usa CC0. Cada
resposta preserva a fonte correspondente. O código do Sisyphus é distribuído
sob a licença MIT.
