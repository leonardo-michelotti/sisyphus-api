# Fontes suplementares

O catálogo principal continua sendo coletado automaticamente do Wikiquote em português. A
fonte suplementar existe para cobrir lacunas editoriais sem misturar transcrição manual com a
coleta automatizada.

## Regra de entrada

Uma frase só pode ser adicionada a `editorial/supplemental_quotes.csv` quando todos os campos
obrigatórios estiverem confirmados:

- autor identificado por QID e nome canônico do catálogo;
- texto em português e, quando for tradução, texto e idioma originais;
- obra ou contexto de publicação;
- URL direta da fonte consultada;
- nome e licença da fonte;
- responsável e licença da tradução;
- data da revisão editorial em UTC.

O pipeline rejeita registros incompletos, QIDs desconhecidos, categorias inválidas, URLs sem
HTTPS e traduções sem crédito ou licença. O arquivo pode permanecer apenas com o cabeçalho. Isso
significa que ainda não há uma fonte suplementar aprovada, não uma falha de ingestão.

## Fluxo editorial

1. Registrar o candidato e conferir a fonte primária ou uma edição confiável.
2. Confirmar que a reprodução do trecho e a tradução são compatíveis com o uso público.
3. Revisar a tradução contra o original e registrar o responsável.
4. Executar o pipeline completo e examinar os testes de qualidade.
5. Promover o `quote_id` resultante para a seleção diária em uma alteração separada.

Uma inclusão na fonte suplementar não torna a frase elegível automaticamente. A allowlist
`daily_quote_selection.csv` continua sendo a decisão editorial final.
