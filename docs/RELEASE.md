# Publicação da base curada

Este procedimento descreve como transformar uma execução validada do pipeline em
uma imagem de runtime identificável e promovê-la com segurança. Cada nova publicação
ou alteração no Railway continua dependendo de autorização explícita.

## Separação entre build e runtime

`Dockerfile.release` é usado depois que o pipeline gera `data/sisyphus.db`. Produção
consome essa imagem pronta, sem reconstruir o código ou a base no Railway. O
`Dockerfile` original permanece apenas como caminho de desenvolvimento e legado.

A imagem de release contém:

- aplicação FastAPI instalada a partir de `uv.lock`;
- SQLite curado em `/app/data/sisyphus.db`;
- usuário sem privilégios `appuser`;
- healthcheck local em `/health/dataset`.

Ela não contém bronze, DuckDB, dbt, testes, documentação interna ou credenciais.

## Identidade e rastreabilidade

Cada SQLite registra:

- versão do schema e do dataset;
- horário mais recente das fontes;
- versões do pipeline e do parser;
- `run_id` e SHA-256 do manifesto;
- commit exato usado na construção.

O workflow prepara uma tag imutável no formato:

```text
ghcr.io/leonardo-michelotti/sisyphus-api:git-<commit>-data-<dataset>
```

O digest OCI é a identidade definitiva da imagem. Quando houver publicação, o
GitHub também gera uma atestação de procedência associada a esse digest.

## Executar sem publicar

Em **Actions > Build curated runtime image > Run workflow**, manter
`publish_image` desabilitado. Essa execução:

1. instala exatamente o lock;
2. executa Ruff, mypy e pytest;
3. coleta as fontes e executa os 28 passos dbt;
4. publica o SQLite apenas no workspace temporário;
5. constrói a imagem local;
6. testa healthcheck e frase do dia;
7. confirma usuário, permissões e ausência dos dados intermediários.

Nenhum pacote é enviado ao GHCR nesse modo.

## Publicar no GHCR

Habilitar `publish_image` somente depois de revisar a execução seca e receber
autorização explícita. O workflow usa `GITHUB_TOKEN`, permissões mínimas e actions
fixadas por SHA. Ele publica uma única tag imutável e sua atestação. Não cria
`latest` e não aciona o Railway.

O pacote atual é público e pode ser consumido anonimamente pelo Railway no plano
Hobby. Pacotes privados exigem suporte do plano a registros privados e uma
credencial com somente `read:packages`.

## Entrada segura no Railway

Fazer o primeiro teste em um serviço temporário, sem substituir o serviço público:

1. apontar o serviço temporário para a tag imutável;
2. configurar `/health/dataset` em **Deploy > Healthcheck Path**;
3. validar `/health`, `/health/dataset`, `/v1/quote-of-the-day` e o OpenAPI;
4. comparar `dataset_version` com o resumo do workflow;
5. simular retorno à imagem anterior;
6. registrar tag, digest, dataset e deployment na governança privada.

Somente depois desse ensaio o serviço público pode ser alterado. Atualização
automática por tag mutável permanece desabilitada.

O `HEALTHCHECK` do `Dockerfile.release` protege a execução do container, mas não
substitui o Healthcheck Path do Railway. É essa configuração da plataforma que
impede a troca de tráfego até `/health/dataset` responder HTTP 200.

## Estado atual

O serviço público consome uma tag imutável do GHCR produzida por esse workflow.
Um `railway up` direto não é o caminho de produção, pois não transporta o SQLite
curado. Mudanças de código seguem o mesmo ciclo de execução seca, publicação da
imagem e promoção explícita da nova tag no Railway.

## Rollback

O rollback primário seleciona o deployment anterior no Railway, que restaura a
imagem e as variáveis daquele deployment. Como a retenção depende do plano, o
registro privado também deve guardar a tag e o digest da última imagem aprovada.

Se o rollback da plataforma não estiver mais disponível:

1. apontar o serviço para a tag imutável anterior;
2. redeployar;
3. conferir `/health/dataset`;
4. confirmar a versão anterior em `/v1/quote-of-the-day`;
5. registrar o incidente e a recuperação.

## Condições que bloqueiam a publicação

- testes, dbt ou auditoria falham;
- SQLite não passa em `pragma integrity_check`;
- alguma personalidade não possui frase diária aprovada;
- commit, manifesto ou metadados divergem;
- imagem executa como root;
- bronze ou DuckDB aparecem no runtime;
- a tag não é imutável ou o Railway não consegue acessar o pacote;
- não existe autorização explícita para publicar ou implantar.
