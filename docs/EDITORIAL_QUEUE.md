# Fila editorial

A rotação pública continua com 54 frases, três para cada um dos 18 pensadores.
A fila prepara a próxima ampliação sem promover candidatos automaticamente.

## Estado atual

- 34 candidatos revisados;
- 31 aprovados para uma futura promoção;
- três rejeitados nesta rodada;
- 17 pensadores representados;
- dois candidatos por pensador representado;
- nenhuma frase da fila já pertence à rotação diária;
- nenhuma frase com referência bibliográfica isolada, atribuição duvidosa, início
  fragmentado ou mais de 500 caracteres.

Marie Curie não aparece na fila. A página atual do Wikiquote em português oferece
somente as três frases que já estão na rotação. A meta de cinco por pensador fica
bloqueada até encontrarmos uma fonte adicional licenciada e verificável.

Uma frase de Hannah Arendt foi rejeitada por ser longa demais para a experiência
diária. Duas frases de Max Weber foram rejeitadas porque o texto de origem precisa
de revisão de transcrição. Essas decisões permanecem na fila como histórico.

## Fluxo de decisão

1. Um candidato entra em `dbt/seeds/quote_review_queue.csv` como `pending`.
2. A revisão confere texto completo, atribuição, obra, fonte, licença e utilidade
   dentro das coleções.
3. O estado muda para `approved` ou `rejected`, com a decisão registrada no commit.
4. Somente candidatos aprovados são copiados para
   `dbt/seeds/daily_quote_selection.csv`.
5. A promoção altera o contrato de quantidade por pensador apenas quando todos os
   autores possuem o mesmo número de frases.

O arquivo da fila não é lido pela API e não altera o SQLite servido. Ele é um
artefato de governança editorial validado pelo dbt.

Depois de executar `python run_pipeline.py transform`, a visão
`editorial_review_queue` no DuckDB apresenta os textos completos, obras, categorias,
motivos de qualidade e fontes associados aos identificadores do CSV.

## Critérios

Um candidato pode avançar quando:

- preserva URL, nome da fonte e licença;
- apresenta uma frase completa e compreensível fora da página original;
- não pertence a uma seção de atribuição duvidosa;
- acrescenta um tema ou tom ainda pouco representado para o autor;
- não repete uma frase já presente na rotação.

Textos curtos ou longos podem ser avaliados manualmente. Referências isoladas,
fragmentos e atribuições duvidosas permanecem bloqueios rígidos.

## Lacunas antes da promoção

Para chegar a cinco frases por pensador ainda faltam:

- duas frases verificáveis de Marie Curie;
- duas substituições para Max Weber;
- uma substituição para Hannah Arendt.

Fontes primárias candidatas para Marie Curie: a autobiografia incluída em
[*Pierre Curie* (1923)](https://www.gutenberg.org/ebooks/69617) e a
[palestra Nobel de 1911](https://www.nobelprize.org/prizes/chemistry/1911/marie-curie/lecture/).
A edição do Project Gutenberg é declarada como domínio público nos Estados Unidos;
o uso da tradução inglesa ainda exige uma análise compatível com a jurisdição do
projeto. Essas fontes precisam entrar no pipeline com texto original, tradução e
proveniência explícitos antes de qualquer promoção.
