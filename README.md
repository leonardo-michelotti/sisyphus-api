<div align="center">

# Sisyphus

Frases com contexto, fonte identificada e uma URL pronta para incorporar.

[![CI](https://github.com/leonardo-michelotti/sisyphus-api/actions/workflows/ci.yml/badge.svg)](https://github.com/leonardo-michelotti/sisyphus-api/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/License-MIT-D4A85A)](LICENSE)

[Abrir o gerador](https://sisyphus-public-production.up.railway.app/) ·
[Explorar a API](https://sisyphus-public-production.up.railway.app/docs) ·
[Ver influências](https://sisyphus-public-production.up.railway.app/influences?thinker=Albert%20Camus)

</div>

> Uma frase melhor escolhida, apresentada com contexto e pronta para ocupar seu
> espaço digital.

O Sisyphus combina Wikiquote e Wikidata para entregar frases de filósofos,
sociólogos, escritores e cientistas. O mesmo núcleo alimenta um widget para uso
sem código, uma API REST versionada e um mapa de influências intelectuais.

## Comece em 30 segundos

Escolha uma coleção no [gerador](https://sisyphus-public-production.up.railway.app/),
defina o ritmo e copie o link. Esta URL, por exemplo, exibe uma frase diária da
coleção Existência e absurdo:

```text
https://sisyphus-public-production.up.railway.app/widget?collection=existencia-e-absurdo&mode=daily
```

A frase diária permanece estável durante a data UTC. Para receber uma nova
seleção a cada carregamento, troque `mode=daily` por `mode=random`.

## Use onde você já trabalha

### Notion

1. No Notion, digite `/embed` e escolha **Embed**.
2. Cole a URL gerada pelo Sisyphus.
3. Confirme a incorporação e ajuste a altura do bloco.

Use `mode=daily` para dashboards, páginas iniciais e diários. O conteúdo muda
uma vez por dia sem exigir automação no workspace.

### Obsidian

Adicione um `iframe` à nota e abra o modo de leitura:

```html
<iframe
  src="https://sisyphus-public-production.up.railway.app/widget?collection=conhecimento-e-duvida&mode=daily"
  width="100%"
  height="320"
  title="Frase do dia"
  loading="lazy"
></iframe>
```

O conteúdo continua vindo do serviço; a nota guarda apenas a configuração do
widget. Para uma nota fixa, copie o texto retornado pela API em vez de usar o
`iframe`.

### Sites, blogs e dashboards

O widget não exige JavaScript nem dependências no front-end:

```html
<iframe
  src="https://sisyphus-public-production.up.railway.app/widget?thinker=Hannah%20Arendt&mode=daily&show_context=true"
  width="100%"
  height="320"
  title="Frase de Hannah Arendt"
  loading="lazy"
  style="border: 0"
></iframe>
```

| Parâmetro | Valores | Função |
|---|---|---|
| `collection` | slug de uma coleção | Restringe a seleção ao recorte editorial |
| `thinker` | nome de uma personalidade | Seleciona frases de uma pessoa |
| `mode` | `daily` ou `random` | Define o ritmo de atualização |
| `show_context` | `true` ou `false` | Exibe categoria, obra e coleção |

## Coleções disponíveis

As coleções organizam personalidades por recortes editoriais. As frases ainda
são obtidas dinamicamente das fontes Wikimedia.

| Coleção | Slug | Recorte |
|---|---|---|
| Existência e absurdo | `existencia-e-absurdo` | Liberdade, sentido e experiência de existir |
| Ciência e curiosidade | `ciencia-e-curiosidade` | Investigação, descoberta e limites do conhecimento |
| Liberdade e responsabilidade | `liberdade-e-responsabilidade` | Escolha, ação política e responsabilidade |
| Sociedade e poder | `sociedade-e-poder` | Estruturas sociais, autoridade e transformação |
| Conhecimento e dúvida | `conhecimento-e-duvida` | Razão, método, incerteza e pensamento crítico |

O catálogo completo, incluindo as personalidades de cada coleção, está em
[`GET /v1/collections`](https://sisyphus-public-production.up.railway.app/v1/collections).

## Use como API

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
<summary>Exemplo de resposta</summary>

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
  "data": "2026-07-12",
  "colecao": null
}
```

O conteúdo e o autor variam conforme a data e os filtros.

</details>

## Recursos

| Quero... | Caminho |
|---|---|
| configurar um widget | [Gerador visual](https://sisyphus-public-production.up.railway.app/) |
| testar os contratos | [Swagger](https://sisyphus-public-production.up.railway.app/docs) |
| consultar o OpenAPI | [`/openapi.json`](https://sisyphus-public-production.up.railway.app/openapi.json) |
| explorar relações intelectuais | [Mapa de influências](https://sisyphus-public-production.up.railway.app/influences?thinker=Albert%20Camus) |
| listar coleções | [`/v1/collections`](https://sisyphus-public-production.up.railway.app/v1/collections) |
| verificar o serviço | [`/health`](https://sisyphus-public-production.up.railway.app/health) |

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
`application/problem+json`. As respostas expõem ETag, cache HTTP, request ID e
headers de rate limit quando aplicável. A seleção aleatória usa
`Cache-Control: no-store`.

## Como funciona

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

As decisões e os limites técnicos estão registrados em
[`docs/DECISIONS.md`](docs/DECISIONS.md),
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e
[`docs/PILARES_TECNICOS.md`](docs/PILARES_TECNICOS.md).

## Desenvolvimento local

Requer Python 3.10 ou superior.

```bash
git clone https://github.com/leonardo-michelotti/sisyphus-api.git
cd sisyphus-api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn sisyphus.main:app --reload
```

No Windows PowerShell, ative o ambiente com:

```powershell
.venv\Scripts\Activate.ps1
```

Configure no `.env` um `User-Agent` válido para as APIs Wikimedia e abra
`http://localhost:8000/docs`.

## Qualidade

```bash
ruff format --check .
ruff check .
mypy
pytest
```

O CI executa Python 3.10 e 3.12, análise estática, tipagem estrita, testes e
auditoria das dependências de runtime.

## Limites atuais

- As frases dependem da estrutura e da disponibilidade do Wikiquote em português.
- O mapa mostra apenas relações P737 declaradas, não toda a história intelectual.
- As coleções curam grupos de personalidades, ainda não cada frase individual.
- O produto é somente leitura e não possui contas ou painel administrativo.

Os próximos experimentos e seus critérios de priorização estão no
[roadmap](docs/ROADMAP.md).

## Fontes e licença

O conteúdo do Wikiquote é atribuído sob CC BY-SA e o Wikidata usa CC0. Cada
resposta preserva a fonte correspondente. O código do Sisyphus é distribuído
sob a licença MIT.
