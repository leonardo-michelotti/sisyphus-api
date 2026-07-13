# Visão de produto

## Definição

Sisyphus é uma API e um gerador de widgets para exibir frases de filósofos,
sociólogos, escritores, cientistas e outras personalidades intelectuais, com
contexto e fonte identificada.

O produto transforma conteúdo aberto do Wikiquote e do Wikidata em duas
superfícies:

1. uma API REST para aplicações e automações;
2. um widget incorporável para Notion, sites e dashboards pessoais.

## Proposta de valor

> Uma frase melhor escolhida, apresentada com contexto e pronta para incorporar.

O diferencial não é apenas sortear citações. Cada resultado preserva autoria,
categoria, obra quando disponível, fonte e licença. No MVP, as coleções
editoriais organizam personalidades por recortes temáticos; as frases continuam
vindo dinamicamente das fontes. Curadoria frase a frase é uma evolução posterior.

## Público

O público principal são pessoas que personalizam espaços digitais: usuários de
Notion, criadores de templates, newsletters, páginas pessoais, dashboards e
telas internas.

Desenvolvedores, educadores, estudantes e criadores de conteúdo formam o público
secundário. Agentes e integrações por MCP continuam como possibilidade futura,
não como requisito do MVP.

## Core do MVP

- busca e perfil de uma personalidade;
- frases atribuídas com proveniência;
- frase aleatória com filtros;
- frase do dia determinística em UTC;
- cinco coleções editoriais de personalidades;
- widget escuro incorporável;
- página simples para configurar e copiar o link;
- Swagger público.
- mapa de influências intelectuais diretas, com proveniência Wikidata.

O MVP não exige conta, banco de dados, painel administrativo ou infraestrutura
adicional. As coleções vivem no código e passam pelo mesmo versionamento da API.

## Catálogo inicial

O recorte inclui personalidades que contribuíram para o pensamento, a ciência,
a cultura e a compreensão da sociedade. As primeiras coleções são:

1. Existência e absurdo;
2. Ciência e curiosidade;
3. Liberdade e responsabilidade;
4. Sociedade e poder;
5. Conhecimento e dúvida.

## Princípios

- **Contexto antes de volume:** uma frase atribuída e explicável vale mais que
  um catálogo grande e opaco.
- **Uso sem código:** o widget deve funcionar ao copiar uma URL.
- **API e interface compartilham o core:** nenhuma regra de seleção é duplicada
  no front-end.
- **Fontes visíveis:** Wikiquote e Wikidata são creditados nas respostas.
- **Escopo pequeno:** novas camadas entram apenas quando melhoram um caso de uso
  concreto.

## Depois do MVP

Expansão do grafo, busca semântica, múltiplos temas visuais e MCP permanecem
como experimentos possíveis. A prioridade será decidida por utilidade observada,
não apenas pelo valor técnico de demonstração.
