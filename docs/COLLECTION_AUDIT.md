# Auditoria das coleções editoriais

Dataset `794ad6ac195b3593`. Cobertura diária **completa**.

- 737 registros coletados;
- 54 frases aprovadas para o modo diário;
- 18 pensadores;
- 3 a 3 frases por pensador;
- 0 textos duplicados no recorte diário.

| Coleção | Cobertura | Frases | Fontes | Com obra | Tamanho min./méd./máx. |
|---|---:|---:|---:|---:|---:|
| Existência e absurdo | 4/4 | 12 | 12 | 9 | 46/91,5/124 |
| Ciência e curiosidade | 4/4 | 12 | 12 | 3 | 83/121,7/224 |
| Liberdade e responsabilidade | 4/4 | 12 | 12 | 6 | 62/90,4/136 |
| Sociedade e poder | 4/4 | 12 | 12 | 5 | 44/114,7/292 |
| Conhecimento e dúvida | 4/4 | 12 | 12 | 10 | 68/106,2/207 |
| Trabalho e vocação | 4/4 | 12 | 12 | 3 | 44/104,4/292 |
| Revolta e resistência | 4/4 | 12 | 12 | 6 | 47/91,9/136 |
| Método e descoberta | 4/4 | 12 | 12 | 5 | 68/115/207 |
| Universo e humanidade | 4/4 | 12 | 12 | 5 | 80/118,7/224 |
| Indivíduo e liberdade | 4/4 | 12 | 12 | 12 | 46/88,9/125 |

## Leitura

Todas as coleções possuem três frases diárias para cada pensador e todas as
54 frases preservam fonte, licença e URL. O campo “Com obra” é informativo: uma
frase pode ser válida mesmo quando a página do Wikiquote não identifica uma obra.

O recorte diário continua deliberadamente curado. Os 737 registros coletados não
são promovidos em massa. Cada pensador recebeu duas novas frases depois de revisão
individual, sem perder a proveniência verificável nem o equilíbrio da rotação.

Para reproduzir a tabela:

```bash
uv run sisyphus-audit --format markdown
```
