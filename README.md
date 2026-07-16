<div align="center">

# Sisyphus

Uma frase, sua fonte e uma URL.

[![CI](https://github.com/leonardo-michelotti/sisyphus-api/actions/workflows/ci.yml/badge.svg)](https://github.com/leonardo-michelotti/sisyphus-api/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/License-MIT-D4A85A)](LICENSE)

[Gerar um widget](https://sisyphus-public-production.up.railway.app/) ·
[Explorar coleções](https://sisyphus-public-production.up.railway.app/collections) ·
[Explorar a API](https://sisyphus-public-production.up.railway.app/docs) ·
[Ver influências](https://sisyphus-public-production.up.railway.app/influences?thinker=Albert%20Camus)

</div>

Eu queria deixar uma frase por perto: numa nota, numa página, talvez ao lado do
café. Sem uma lista de citações soltas e sem esconder de onde o texto veio. O
Sisyphus nasceu daí.

Ele faz três coisas:

- escolhe uma frase diária revisada;
- oferece uma seleção aleatória para explorar;
- entrega tudo como widget ou JSON.

No ar: <https://sisyphus-public-production.up.railway.app>

## Experimente primeiro

Esta URL mostra uma frase diária da coleção **Existência e absurdo**:

```text
https://sisyphus-public-production.up.railway.app/widget?collection=existencia-e-absurdo&mode=daily
```

Para receber outra seleção a cada carregamento, use `mode=random`. Também é
possível filtrar por pensador:

```text
https://sisyphus-public-production.up.railway.app/widget?thinker=Hannah%20Arendt&mode=daily&show_context=true
```

O [gerador visual](https://sisyphus-public-production.up.railway.app/) monta a URL
sem que seja necessário editar os parâmetros manualmente.

## Incorporar o widget

### Notion

1. Digite `/embed` e escolha **Embed**.
2. Cole a URL produzida pelo gerador.
3. Confirme e ajuste a altura do bloco.

O modo `daily` funciona bem em páginas iniciais e diários porque o conteúdo muda
uma vez por dia sem exigir automação no workspace.

### Obsidian, sites e blogs

```html
<iframe
  src="https://sisyphus-public-production.up.railway.app/widget?collection=conhecimento-e-duvida&mode=daily"
  width="100%"
  height="320"
  title="Frase do dia"
  loading="lazy"
  style="border: 0"
></iframe>
```

No Obsidian, o `iframe` aparece no modo de leitura. A nota guarda apenas a
configuração; o conteúdo continua sendo servido pelo Sisyphus.

| Parâmetro | Valores | Efeito |
|---|---|---|
| `collection` | slug de uma coleção | Restringe a seleção ao recorte editorial |
| `thinker` | nome de uma personalidade | Seleciona uma pessoa |
| `mode` | `daily` ou `random` | Define quando a frase muda |
| `show_context` | `true` ou `false` | Exibe obra, categoria e coleção |
| `max_length` | de 40 a 1000 | Limita o tamanho da frase |

## Usar como API

URL base:

```text
https://sisyphus-public-production.up.railway.app
```

### Frase do dia

```bash
curl "https://sisyphus-public-production.up.railway.app/v1/quote-of-the-day?collection=ciencia-e-curiosidade&max_length=220"
```

### Frase aleatória

```bash
curl "https://sisyphus-public-production.up.railway.app/v1/quotes/random?thinker=Simone%20de%20Beauvoir"
```

### JavaScript

```javascript
const url = new URL(
  "https://sisyphus-public-production.up.railway.app/v1/quote-of-the-day"
);
url.searchParams.set("collection", "conhecimento-e-duvida");
url.searchParams.set("max_length", "220");

const response = await fetch(url);
if (!response.ok) throw new Error(`Sisyphus respondeu ${response.status}`);

const selection = await response.json();
console.log(`${selection.frase.texto} — ${selection.frase.autor}`);
```

### Python

```python
import httpx

url = "https://sisyphus-public-production.up.railway.app/v1/quote-of-the-day"
params = {"collection": "sociedade-e-poder", "max_length": 220}

response = httpx.get(url, params=params, timeout=10)
response.raise_for_status()

selection = response.json()
print(f'{selection["frase"]["texto"]} — {selection["frase"]["autor"]}')
```

<details>
<summary>Formato da resposta</summary>

```json
{
  "frase": {
    "texto": "...",
    "autor": "Albert Camus",
    "categoria": "verificada",
    "obra": null,
    "original": null,
    "fonte": {
      "fonte": "Wikiquote",
      "licenca": "CC BY-SA 4.0",
      "url": "https://pt.wikiquote.org/wiki/Albert_Camus"
    }
  },
  "modo": "daily",
  "data": "AAAA-MM-DD",
  "colecao": null,
  "dataset_version": "hash-do-dataset",
  "dataset_schema": 2
}
```

</details>

Listas usam o envelope `{data, meta}`. Erros seguem RFC 9457 em
`application/problem+json`. As respostas incluem ETag, cache HTTP, request ID e
limites de requisição quando aplicável. A seleção aleatória usa
`Cache-Control: no-store`.

### Endpoints principais

| Método | Rota | Retorna |
|---|---|---|
| `GET` | `/v1/quote-of-the-day` | Frase diária curada e determinística |
| `GET` | `/v1/quotes/random` | Frase aleatória com filtros |
| `GET` | `/v1/collections` | Coleções editoriais |
| `GET` | `/v1/search?q=` | Busca de personalidades |
| `GET` | `/v1/thinkers/{nome}` | Perfil, obras e amostra de frases |
| `GET` | `/v1/thinkers/{nome}/quotes` | Frases paginadas |
| `GET` | `/v1/thinkers/{nome}/influences` | Influências diretas via Wikidata P737 |
| `GET` | `/health` | Estado do processo |
| `GET` | `/health/dataset` | Integridade e versão da base curada |

O contrato completo está no [Swagger](https://sisyphus-public-production.up.railway.app/docs)
e em [`/openapi.json`](https://sisyphus-public-production.up.railway.app/openapi.json).

## Coleções editoriais

| Coleção | Slug | Recorte |
|---|---|---|
| Existência e absurdo | `existencia-e-absurdo` | Liberdade, sentido e experiência de existir |
| Ciência e curiosidade | `ciencia-e-curiosidade` | Investigação, descoberta e limites do conhecimento |
| Liberdade e responsabilidade | `liberdade-e-responsabilidade` | Escolha, ação política e responsabilidade |
| Sociedade e poder | `sociedade-e-poder` | Estruturas sociais, autoridade e transformação |
| Conhecimento e dúvida | `conhecimento-e-duvida` | Razão, método, incerteza e pensamento crítico |
| Trabalho e vocação | `trabalho-e-vocacao` | Trabalho, ação e vida pública |
| Revolta e resistência | `revolta-e-resistencia` | Recusa, coragem e transformação |
| Método e descoberta | `metodo-e-descoberta` | Dúvida, experimento e conhecimento |
| Universo e humanidade | `universo-e-humanidade` | Cosmos, ciência e lugar humano |
| Indivíduo e liberdade | `individuo-e-liberdade` | Autonomia, escolha e convivência |

O catálogo completo, com as personalidades de cada coleção, está em
[`GET /v1/collections`](https://sisyphus-public-production.up.railway.app/v1/collections).

## Por dentro

O Sisyphus é uma API somente leitura. Um pipeline separado coleta e organiza o
conteúdo; a aplicação recebe um SQLite já revisado para servir a frase do dia.

```text
Wikiquote + Wikidata
        │
        ▼
Python + HTTPX
        │
        ▼
bronze: JSON + Parquet
        │
        ▼
dbt-duckdb: silver + gold + testes
        │
        ▼
SQLite + FTS5 + metadados de versão
        │
        ▼
FastAPI ──────► REST JSON
        ├─────► widget HTML
        └─────► mapa de influências
```

O runner `run_pipeline.py` encadeia coleta, transformação, publicação e auditoria.
Casos duvidosos ficam separados para revisão. A frase diária usa apenas o recorte
aprovado e não troca silenciosamente para a fonte ao vivo.

Detalhes:

- [arquitetura](docs/ARQUITETURA.md);
- [pipeline de dados](docs/DATA_PIPELINE.md);
- [decisões técnicas](docs/DECISIONS.md);
- [processo de release](docs/RELEASE.md);
- [visão e roadmap](docs/PRODUCT_VISION.md).

## Desenvolvimento local

Requer Python 3.10 ou superior.

```bash
git clone https://github.com/leonardo-michelotti/sisyphus-api.git
cd sisyphus-api
python -m pip install "uv==0.11.28"
uv sync --frozen --extra dev
cp .env.example .env
uv run uvicorn sisyphus.main:app --reload
```

Configure no `.env` um `User-Agent` válido para as APIs Wikimedia e abra
`http://localhost:8000/docs`.

### Qualidade

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run sisyphus-audit --format markdown
```

O `uv.lock` fixa a aplicação e as ferramentas do pipeline. O CI cobre Python 3.10
e 3.12, formatação, análise estática, tipagem, testes e auditoria de dependências.
O relatório atual de cobertura está em
[`docs/COLLECTION_AUDIT.md`](docs/COLLECTION_AUDIT.md).

## O que ele não tenta ser

- Frase aleatória, busca, perfis e influências ainda dependem da disponibilidade e
  da estrutura das fontes Wikimedia.
- O mapa mostra relações P737 declaradas no Wikidata, não uma história intelectual
  completa.
- A curadoria individual está aplicada à frase do dia; as demais rotas continuam
  no caminho ao vivo.
- Não há contas, feed social ou painel administrativo.

É uma solução simples, e deve continuar parecendo uma. Os próximos ajustes estão no
[roadmap](docs/ROADMAP.md).

## Fontes e licença

O conteúdo do Wikiquote é atribuído sob CC BY-SA, enquanto o Wikidata usa CC0.
Cada resposta preserva sua fonte. O código do Sisyphus é distribuído sob a
[licença MIT](LICENSE).
