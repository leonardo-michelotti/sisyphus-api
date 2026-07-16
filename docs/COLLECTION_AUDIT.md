# Auditoria das coleções editoriais

Dataset `64c1d628a66bfd0a`. Cobertura diária **completa**.

- 737 registros coletados;
- 18 frases aprovadas para o modo diário;
- 18 pensadores;
- 0 textos duplicados no recorte diário.

| Coleção | Cobertura | Frases | Fontes | Com obra | Tamanho min./méd./máx. |
|---|---:|---:|---:|---:|---:|
| Existência e absurdo | 4/4 | 4 | 4 | 3 | 46/56,5/78 |
| Ciência e curiosidade | 4/4 | 4 | 4 | 1 | 102/136,2/224 |
| Liberdade e responsabilidade | 4/4 | 4 | 4 | 2 | 72/102,8/136 |
| Sociedade e poder | 4/4 | 4 | 4 | 1 | 54/85,5/136 |
| Conhecimento e dúvida | 4/4 | 4 | 4 | 3 | 68/74,8/80 |
| Trabalho e vocação | 4/4 | 4 | 4 | 1 | 54/87,2/136 |
| Revolta e resistência | 4/4 | 4 | 4 | 2 | 47/83,2/136 |
| Método e descoberta | 4/4 | 4 | 4 | 2 | 68/86/102 |
| Universo e humanidade | 4/4 | 4 | 4 | 1 | 80/130,8/224 |
| Indivíduo e liberdade | 4/4 | 4 | 4 | 4 | 46/74,5/125 |

## Leitura

Todas as coleções possuem ao menos uma frase diária para cada pensador e todas as
18 frases preservam fonte, licença e URL. O campo “Com obra” é informativo: uma
frase pode ser válida mesmo quando a página do Wikiquote não identifica uma obra.

O recorte diário continua deliberadamente pequeno. Os 737 registros coletados não
são promovidos em massa; somente 18 passaram pela regra editorial vigente. Antes
de aumentar esse número, a prioridade é revisar casos individuais e manter a
proveniência verificável.

Para reproduzir a tabela:

```bash
uv run sisyphus-audit --format markdown
```
