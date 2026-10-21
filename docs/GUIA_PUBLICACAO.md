# Guia de publicação fora do computador local

Este guia descreve como publicar o Vigil em um domínio acessível pela equipe e fornece um prompt de implementação para outra IA. Ele se baseia na arquitetura e nas configurações presentes no repositório. Não pressupõe um provedor específico: hospedagem, domínio, região, rede privada e método de autenticação precisam ser escolhidos para o ambiente da organização.

## Arquitetura recomendada

```text
Navegador da equipe
        │ HTTPS
        ▼
Frontend Next.js no domínio da aplicação
        │ proxy interno de /api/*, via API_URL
        ▼
API FastAPI, preferencialmente em rede privada
        │ conexão TLS com Oracle Wallet
        ▼
Oracle Database ─── Oracle APEX para revisão de analistas
```

O navegador deve acessar o domínio do frontend. A configuração existente em `web/next.config.ts` encaminha `/api/*` do Next.js ao serviço FastAPI definido por `API_URL`; assim, o endereço interno da API e as credenciais do banco não precisam ser entregues ao navegador. O servidor Next.js precisa conseguir alcançar a API pela rede do provedor.

O frontend usa Next.js com servidor Node.js e a reescrita externa configurada no `next.config.ts`. Não publique o frontend como um conjunto de arquivos estáticos sem antes substituir essa integração. Configure `API_URL` no ambiente de build do frontend e reconstrua o aplicativo se o destino mudar.

## Requisitos antes da publicação

1. Escolher a infraestrutura aprovada pela organização para executar um servidor Node.js e um serviço Python/FastAPI. Confirmar que o servidor web pode acessar a API pela rede privada ou por HTTPS.
2. Ter um domínio e TLS/HTTPS configurados para a aplicação. Não transmitir respostas do formulário por HTTP público.
3. Definir como a equipe será autenticada e autorizada. O formulário atual não implementa login; CORS e validação de `Origin` não autenticam quem envia uma solicitação. Para dados de saúde, proteja a aplicação com os controles de acesso da organização, como SSO ou um proxy de identidade, e garanta que a API não possa ser contornada por acesso direto.
4. Decidir se o formulário deve gravar em Oracle desde o lançamento. Mantenha `TRIAGE_FORM_ENABLED=false` enquanto a autenticação, as permissões APEX, a auditoria e a retenção não estiverem verificadas.
5. Disponibilizar os dados analíticos ao backend. Para `DATA_SOURCE=csv`, forneça os CSVs no ambiente de execução; para `DATA_SOURCE=oracle`, prepare `PRATA` e a conexão Oracle. A API carrega os dados analíticos na inicialização.
6. Providenciar uma conexão Oracle de menor privilégio, acesso de rede de saída ao banco e os arquivos de wallet por um mecanismo seguro do provedor. Não inclua credenciais ou wallet na imagem, no repositório ou em prompts enviados a serviços externos.

## Configuração por serviço

### Frontend Next.js

Configure no ambiente de build:

```dotenv
API_URL=https://<endereco-da-api-alcancavel-pelo-next>
```

O endereço pode ser interno ao provedor, desde que o processo Next.js consiga alcançá-lo. O navegador continua acessando caminhos relativos como `/api/meta` e `/api/pacientes/avaliacao` no domínio do frontend.

Comandos de referência:

```powershell
npm ci
npm run build
npm run start -- --hostname 0.0.0.0 --port 3000
```

Em uma plataforma que injeta a porta por variável, adapte o comando de inicialização para usar a porta fornecida pelo serviço. Mantenha o processo Next.js ativo; não use `npm run dev` como servidor público de produção.

### API FastAPI

Configure as variáveis no ambiente de execução da API, usando o gerenciador de segredos da infraestrutura:

```dotenv
DATA_SOURCE=csv
DENGUE_DATA_DIR=<diretorio-dos-dados-se-necessario>
API_CORS_ORIGINS=https://<dominio-publico-do-frontend>
TRIAGE_FORM_ENABLED=false
VIGIL_DQ_SCHEMA=VIGIL_APEX
DB_USER=<usuario-oracle>
DB_PASSWORD=<segredo>
DB_DSN=<dsn-oracle>
WALLET_DIR=<diretorio-seguro-do-wallet>
WALLET_PASSWORD=<segredo>
```

`DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_DIR` e `WALLET_PASSWORD` são necessários para o envio ao Oracle, independentemente de a fonte analítica ser CSV ou Oracle. Se `DATA_SOURCE=oracle`, configure também `ORACLE_API_TABLE=PRATA`. Se os dados vierem de CSV, forneça os arquivos necessários em `DENGUE_DATA_DIR` ou no diretório padrão do projeto.

Defina `API_CORS_ORIGINS` com a origem HTTPS exata do site, incluindo protocolo e porta quando não padrão, sem barra final. Em ambientes com mais de uma origem autorizada, separe-as por vírgulas. Essa configuração apoia a política do navegador e não substitui autorização.

Comando de referência para iniciar o serviço:

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Use a porta definida pelo provedor quando aplicável. Termine TLS em um balanceador/proxy HTTPS gerenciado e restrinja o acesso de rede direto à API, se o provedor permitir. `GET /api/meta` pode ser usado para verificar se a API iniciou e carregou sua fonte de dados; uma resposta bem-sucedida não valida a gravação Oracle.

### Oracle e APEX

Execute os scripts SQL no schema aprovado, em uma instância de desenvolvimento/homologação primeiro:

1. `sql/create_data_quality_tables.sql`
2. `sql/create_data_quality_workflow.sql`
3. `sql/create_triage_intake.sql`

Confirme que a conexão da API usa o schema esperado em `VIGIL_DQ_SCHEMA`, que o usuário tem somente as permissões necessárias e que os analistas acessam a fila APEX com autorização. O primeiro script de acolhimento cria uma tabela e não deve ser repetido sobre uma tabela já existente.

Crie no APEX o relatório sobre `VIGIL_TRIAGE_REVIEW_QUEUE` e a ação autenticada de revisão descrita no [README](../README.md). A API e o APEX devem usar o mesmo schema e a mesma tabela compartilhada.

## Controles de segurança obrigatórios para o formulário

O estado atual do código exige um `Origin` permitido e uma flag de habilitação para aceitar o envio, mas isso não impede um cliente externo de construir uma requisição HTTP diretamente. Antes de habilitar a gravação em um ambiente acessível pela internet:

- proteja o acesso ao frontend e à rota de submissão com autenticação e autorização institucional;
- impeça o acesso direto não autenticado à API ou ao endpoint de gravação;
- aplique rate limiting, limites de requisição e monitoramento de erros;
- restrinja as permissões do usuário Oracle à tabela e operações necessárias;
- defina auditoria, retenção e remoção dos dados com os responsáveis da organização;
- use apenas dados sintéticos durante testes e validação técnica;
- não habilite submissões reais até que esses controles sejam verificados.

Não crie credenciais ou compartilhe chaves, senhas, arquivos wallet ou dados de pacientes em conversas com outra IA. A autenticação de infraestrutura deve proteger também os caminhos de API encaminhados pelo Next.js.

## Verificação após a publicação

1. Acesse o site pelo domínio HTTPS e confirme que a interface e os painéis carregam.
2. Verifique `GET /api/meta` através do caminho do frontend, por exemplo `https://<dominio>/api/meta`.
3. Em homologação, com autorização habilitada, envie uma avaliação sintética e confirme que a página mostra o protocolo.
4. Confirme que o mesmo protocolo aparece em `VIGIL_TRIAGE_REVIEW_QUEUE`, com a flag e os campos faltantes esperados.
5. Teste que um usuário sem autorização não acessa a tela protegida nem consegue submeter diretamente à rota de API.
6. Revise logs e monitore falhas de rede, disponibilidade do Oracle e reinicializações. Não registre conteúdo clínico desnecessário.

## Prompt para entregar a outra IA

Copie o texto abaixo para a IA que ajudará na publicação. Informe o provedor, domínio e ambiente quando forem conhecidos. Se ainda não foram definidos, peça à IA que faça essas perguntas antes de propor comandos específicos.

> Quero publicar este repositório Vigil em um endereço HTTPS acessível pela equipe, sem depender de `localhost`. Primeiro, inspecione o repositório e confirme a arquitetura existente: frontend Next.js em `web/`, API FastAPI em `api/`, reescrita de `/api/*` por `API_URL` em `web/next.config.ts`, acesso Oracle feito somente no backend e revisão da fila no Oracle APEX. Leia `README.md` e `docs/GUIA_PUBLICACAO.md`.
>
> Não assuma um provedor, domínio, região, arquitetura de rede ou método de autenticação que eu não tenha informado. Se esses dados forem necessários e estiverem ausentes, pergunte-os antes de gerar configuração específica. Não solicite nem revele senhas, chaves, dados de pacientes ou conteúdo de wallet; indique somente os nomes das variáveis que devo preencher em um gerenciador de segredos.
>
> Prepare uma publicação reproduzível para o provedor escolhido, mantendo o Next.js como servidor Node.js e a API FastAPI separada. Configure o Next.js para encaminhar `/api/*` ao destino `API_URL` alcançável pelo servidor web. Mantenha as credenciais Oracle exclusivamente no serviço FastAPI, com wallet injetado de forma segura, e nunca exponha Oracle diretamente à internet. Explique quais variáveis pertencem ao build do frontend e quais pertencem ao runtime da API. Não use `npm run dev` em produção.
>
> A aplicação não possui autenticação própria no formulário. Não trate CORS, cabeçalho `Origin` ou endereço difícil de adivinhar como autenticação. Antes de habilitar gravações, proponha e implemente, se eu autorizar, uma proteção institucional de acesso que cubra o frontend e a rota de submissão, bloqueie acesso direto à API, inclua rate limiting e mantenha a experiência sem login embutido solicitada para o formulário quando isso puder ser feito pelo SSO/proxy aprovado. Se não houver uma solução de acesso compatível com o provedor escolhido, mantenha `TRIAGE_FORM_ENABLED=false` e explique o bloqueio; não publique a rota de gravação desprotegida.
>
> Não altere a lógica clínica nem transforme a completude dos campos em diagnóstico ou prioridade. Não execute DDL, não grave no Oracle de produção e não habilite submissões reais sem minha autorização explícita. Faça primeiro a validação automatizada existente (`python -m unittest discover -s tests -v`; no diretório `web`, `npm test`, `npm run typecheck`, `npm run lint` e `npm run build`). Se mexer em código ou infraestrutura, apresente o diff, execute os testes pertinentes e reporte claramente o que foi validado e o que depende de credenciais ou ações minhas.
>
> Ao final, entregue os serviços e comandos de build/start, variáveis de ambiente por serviço (somente nomes, nunca valores secretos), configuração de domínio e HTTPS, regra de rede Next.js → API e API → Oracle, controles de acesso, processo de deploy/rollback e testes de smoke com dados sintéticos. Não afirme que a aplicação está publicada ou conectada ao Oracle se isso não tiver sido efetivamente confirmado.
