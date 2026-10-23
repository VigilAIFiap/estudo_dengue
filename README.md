# Vigil — Plataforma de inteligência epidemiológica da dengue

Aplicação web para explorar notificações de dengue, comparar indicadores epidemiológicos e apoiar a revisão de completude de dados recebidos por um formulário de acolhimento. A solução é composta por um frontend Next.js, uma API FastAPI e integrações opcionais com Oracle Database e Oracle APEX.

> O painel e o formulário são ferramentas de informação e revisão administrativa. Não fornecem diagnóstico, recomendação clínica nem prioridade de atendimento.

## Visão geral

| Componente | Diretório | Responsabilidade |
|---|---|---|
| Interface web | `web/` | Next.js, TypeScript, painéis epidemiológicos e formulário de acolhimento. |
| API | `api/` | FastAPI, carregamento dos dados analíticos, consultas e recebimento do formulário. |
| ETL e modelos | `src/` | Preparação das camadas Bronze, Prata e Ouro, carga Oracle e modelos experimentais. |
| Scripts Oracle | `sql/` | DDL para tabelas analíticas, staging e filas de revisão APEX. |
| Testes | `tests/`, `web/src/__tests__/` | Testes de API, dados, integrações e interface. |

O painel Streamlit legado não faz parte da aplicação atual. O frontend e a API são serviços separados. Em desenvolvimento, o Next.js encaminha `/api/*` à API através de uma reescrita configurada por `API_URL`.

## Requisitos

- Python 3.11 ou superior.
- Node.js 20.9 ou superior e npm.
- Para leitura e gravação Oracle: acesso de rede ao banco, usuário Oracle autorizado e wallet configurado fora do repositório.
- Para o modo CSV: os arquivos de dados necessários em `dados/raw/` ou em `DENGUE_DATA_DIR`.

## Configuração local

Na raiz do repositório, instale as dependências e crie o arquivo de configuração local:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

O modo analítico padrão é `DATA_SOURCE=csv`. Confira se `dados/raw/` contém `DENGBR23.csv`, `DENGBR24.csv`, `DENGBR25.csv`, `DENGBR26.csv` e `municipios.csv`. Para usar outro diretório, configure `DENGUE_DATA_DIR`.

Por padrão, os casos são contados no município de notificação (`ID_MUNICIP`). Com `DENGUE_MUNICIPIO_BASE=residencia`, a API usa o município de residência do paciente (`ID_MN_RESI`), o que reduz os municípios sem notificação; isso exige a coluna `ID_MN_RESI` em todos os arquivos. `GET /api/meta` informa `base_municipal` e quantas notificações ficaram sem residência válida (`sem_residencia`).

Para que o formulário grave no Oracle, configure no `.env` do backend as variáveis `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_DIR`, `WALLET_PASSWORD` e `VIGIL_DQ_SCHEMA`. Mantenha `TRIAGE_FORM_ENABLED=false` até instalar e validar as tabelas Oracle. Nunca grave credenciais ou arquivos wallet no Git.

## Iniciar a aplicação

Abra dois terminais na raiz do repositório.

**Terminal 1 — API:**

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```powershell
Set-Location web
npm ci
npm run dev
```

Acesse `http://localhost:3000`. A documentação interativa da API fica em `http://localhost:8000/docs`. O Next.js usa `http://127.0.0.1:8000` como destino padrão do proxy local. Para outro destino, configure `API_URL`; em produção, esse valor deve apontar para a API alcançável pelo servidor Next.js e deve estar disponível quando o aplicativo for construído.

## Testar o fluxo do formulário com dados sintéticos

O teste completo de integração grava uma linha no Oracle. Use somente respostas fictícias e um schema de desenvolvimento ou homologação. Não faça este teste em produção sem autorização, controles de acesso e política de retenção aprovados.

### 1. Instalar os objetos Oracle

Conecte-se no schema destinado à integração e execute **uma vez**, nesta ordem:

1. `sql/create_data_quality_tables.sql`
2. `sql/create_data_quality_workflow.sql`
3. `sql/create_triage_intake.sql`

Os dois primeiros scripts preparam o fluxo de qualidade de cargas CSV. O terceiro cria `VIGIL_TRIAGE_INTAKE`, a view `VIGIL_TRIAGE_REVIEW_QUEUE` e o pacote de revisão `VIGIL_TRIAGE_REVIEW`. Esses objetos são separados das tabelas Prata e Ouro. O script da tabela de acolhimento contém `CREATE TABLE` e não deve ser repetido depois que a tabela já existe.

### 2. Configurar e iniciar a API

No `.env` da raiz, preencha as credenciais Oracle e configure:

```dotenv
API_CORS_ORIGINS=http://localhost:3000
TRIAGE_FORM_ENABLED=true
VIGIL_DQ_SCHEMA=VIGIL_APEX
```

Use em `VIGIL_DQ_SCHEMA` o schema ativo da conexão Oracle, que deve conter a tabela criada no passo anterior. Configure os valores reais do usuário, DSN e wallet de acordo com o ambiente; não os inclua em comandos compartilhados ou no Git. Reinicie a API depois de alterar o `.env`.

Confirme que o serviço iniciou sem erro de carregamento dos dados e abra `http://localhost:8000/docs`. Com `TRIAGE_FORM_ENABLED=false`, o endpoint retorna `503` e não grava dados.

### 3. Enviar uma submissão fictícia

Abra `http://localhost:3000/pacientes`, preencha alguns campos com respostas fictícias, deixe outros como **Não informado** e selecione **Enviar para avaliação**. A tela deve confirmar um número de registro recebido da API. Uma mensagem de falha significa que a API, a configuração Oracle, a tabela ou a origem autorizada precisam ser verificadas; a interface não deve ser considerada confirmação de gravação quando não exibir o protocolo.

Também é possível enviar um exemplo sintético pelo proxy do frontend:

```powershell
$body = @{
  age_group = "20-39"
  sex = "F"
  symptom_duration = "1-3_DIAS"
  fever = "SIM"
  headache = $null
  muscle_pain = "SIM"
  rash = $null
  nausea = "NAO"
  vomiting = $null
  pregnancy = "NAO"
  comorbidities = $null
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:3000/api/pacientes/avaliacao" `
  -Method Post `
  -Headers @{ Origin = "http://localhost:3000" } `
  -ContentType "application/json" `
  -Body $body
```

A resposta esperada tem um `intake_id` numérico e o status `PENDENTE`. Cada submissão confirmada cria uma nova linha.

### 4. Confirmar a fila no APEX

No SQL Workshop do APEX, execute:

```sql
SELECT
    INTAKE_ID,
    RECEIVED_AT,
    STATUS,
    AGE_GROUP,
    SEX,
    SYMPTOM_DURATION,
    FEVER,
    ALERTA_DADOS_FALTANTES,
    CAMPOS_FALTANTES
FROM VIGIL_TRIAGE_REVIEW_QUEUE
WHERE INTAKE_ID = 12345;
```

Substitua `12345` pelo protocolo numérico retornado pela API. O registro deve aparecer como `PENDENTE`, com as respostas enviadas; para o exemplo acima, `ALERTA_DADOS_FALTANTES` deve ser `SIM`, e `CAMPOS_FALTANTES` deve listar campos como `CEFALEIA`, `ERUPCAO_CUTANEA`, `VOMITO` e `COMORBIDADES`. A view lista somente registros `PENDENTE` ou `EM_ANALISE`; após concluir a revisão, o registro sai da fila aberta.

### 5. Executar e validar os testes automatizados

Na raiz do repositório:

```powershell
python -m unittest discover -s tests -v
```

No frontend:

```powershell
Set-Location web
npm test
npm run typecheck
npm run lint
npm run build
```

Os testes automatizados usam dados e dependências simulados; não substituem o teste de integração manual com um Oracle de homologação.

## Dados epidemiológicos

`DATA_SOURCE=csv` carrega os arquivos anuais e `municipios.csv` no início da API; o conjunto processado fica em memória até a reinicialização. A ingestão anual confere `NU_ANO` e aplica as regras definidas no código de dados. `GET /api/meta` informa a fonte e os dados carregados.

Para usar a tabela Oracle Prata como fonte analítica, configure `DATA_SOURCE=oracle`, `ORACLE_API_TABLE=PRATA` e as credenciais/wallet no ambiente da API. Execute a carga e valide a tabela no Oracle antes de alterar essa configuração. O carregamento Oracle ocorre na inicialização e os dados são mantidos em memória para as consultas; não há agregação SQL sob demanda.

As fontes públicas utilizadas no projeto incluem [SINAN/DATASUS](http://www2.datasus.gov.br/DATASUS/index.php), [INMET](https://portal.inmet.gov.br/) e [CPTEC/INPE](https://www.cptec.inpe.br/).

## Camadas Bronze, Prata e Ouro

O pipeline e os scripts Oracle ficam em `src/` e `sql/`. A criação das tabelas analíticas está em `sql/create_prata_ouro.sql`; a staging, em `sql/create_staging_tables.sql`. O fluxo local padrão de preparação e revisão é:

```powershell
python src\auditar_fontes.py
python src\read_data_bronze.py
python src\etl.py --batch-size 25000
python src\gerar_gold.py
python src\oracle_upload.py --review-only
```

Após revisar os dados, `python src\oracle_upload.py` carrega as tabelas de staging e valida contagens e agregados sem substituir `PRATA` e `OURO`. A substituição de produção é uma operação separada, destrutiva e explicitamente confirmada; exige backup, revisão de staging e aprovação do responsável Oracle. Não use `--mode replace --confirm-replace` como parte de uma rotina automática.

O fluxo administrativo de qualidade CSV está separado do formulário de acolhimento. `src/oracle_quality_upload.py` oferece prévia local e grava em tabelas de qualidade somente com `--confirm-import`.

## Segurança e privacidade

O formulário não coleta nome, CPF, endereço, telefone ou texto livre, mas as respostas continuam sendo dados de saúde. Use dados sintéticos para desenvolvimento, limite o acesso ao Oracle/APEX, defina retenção e auditoria e não exponha o formulário publicamente sem autenticação e controles de acesso adequados.

`API_CORS_ORIGINS` restringe origens de navegador; a validação do cabeçalho `Origin` **não é autenticação** e pode ser falsificada por clientes fora do navegador. O endpoint de gravação não deve ficar publicamente acessível com `TRIAGE_FORM_ENABLED=true` sem uma camada de controle de acesso e proteção contra abuso. O frontend não recebe credenciais Oracle; somente o backend deve acessar o banco. Para orientação de implantação fora do computador local, consulte [Guia de publicação e prompt de implantação](docs/GUIA_PUBLICACAO.md). Para publicar a API (Docker), a carga no Oracle e o front na Vercel, veja [Publicar o projeto](docs/DEPLOY_VERCEL.md).

## Modelos experimentais

`src/modelos/` contém modelos temporais e classificadores experimentais independentes da interface. Previsões e classificações exigem validação com dados representativos e revisão profissional. Não são diagnóstico, recomendação clínica nem substitutos da decisão da equipe de saúde.
