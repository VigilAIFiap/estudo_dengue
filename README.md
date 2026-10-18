# Vigil — Plataforma de inteligência epidemiológica da dengue

Painel analítico para gestores públicos acompanharem notificações de dengue, compararem indicadores e identificarem municípios prioritários.

## Estrutura do projeto

| Parte | Diretório | Responsabilidade |
|---|---|---|
| API analítica | `api/` | FastAPI, análise de dados e contratos OpenAPI. |
| Frontend | `web/` | Next.js e TypeScript. |
| ETL e modelos | `src/` | Camadas de dados, integração Oracle, criticidade e modelos preditivos. |
| Testes | `tests/` | Testes da API, ETL e modelos. |

O painel Streamlit antigo foi descartado. A interface atual é a aplicação Next.js.

## Executar localmente

Pré-requisitos: Python 3.11+ e Node.js 20.9+.

1. Instale as dependências Python e crie o arquivo de ambiente:

   ```powershell
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

   A API usa os CSVs em `dados/` (ou no diretório configurado em `DENGUE_DATA_DIR`). Para o Vigil Assist, preencha `ANTHROPIC_API_KEY`. A API analítica lê os arquivos locais e **não acessa o Oracle**.

2. Inicie a API a partir da raiz do repositório:

   ```powershell
   python -m uvicorn api.main:app --reload --port 8000
   ```

3. Em outro terminal, inicie o frontend:

   ```powershell
   Set-Location web
   npm ci
   npm run dev
   ```

   O frontend fica em `http://localhost:3000` e a documentação da API em `http://localhost:8000/docs`. Em Windows, `iniciar.bat` pode iniciar os dois serviços.

Para produção, configure `API_URL` em `web/.env.local` antes do build; o endereço da API é incorporado ao proxy no momento do build.

## Testes

```powershell
python -m unittest discover -s tests -v
Set-Location web
npm test
npm run typecheck
```

## Dados e fontes

A API carrega `DENGBR25.csv`, `DENGBR26.csv` e `municipios.csv` de `dados/` uma vez ao iniciar. O diretório pode ser alterado com `DENGUE_DATA_DIR`. Notificações com data futura ou inválida são descartadas. As fontes incluem [SINAN/DATASUS](http://www2.datasus.gov.br/DATASUS/index.php), [INMET](https://portal.inmet.gov.br/), [CPTEC/INPE](https://www.cptec.inpe.br/) e [CNES](http://cnes.datasus.gov.br/).

## Camadas Prata e Ouro no Oracle

Os Parquets `dados/df_prata.parquet` e `dados/df_ouro.parquet` podem ser carregados nas tabelas Oracle `PRATA` e `OURO`. O DDL está em `sql/create_prata_ouro.sql`; execute-o no schema desejado antes da primeira carga. As credenciais Oracle são usadas apenas pelos scripts de ETL/carga, não pela API.

Configure `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_DIR` e `WALLET_PASSWORD` no `.env`. Nunca publique o wallet ou credenciais.

Os dados e arquivos wallet diferentes que estavam na cópia antiga foram preservados localmente em `dados_wallet_pendente_validacao/`. Essa pasta é ignorada pelo Git; compare os arquivos antes de decidir se alguma versão pode ser removida.

```powershell
python src\etl.py
python src\gerar_gold.py
python src\oracle_upload.py --review-only
python src\oracle_upload.py
```

A carga substitui os dados de ambas as tabelas na mesma transação; em caso de erro, executa rollback. O script não cria as tabelas nem usa `TRUNCATE`.

## Modelos preditivos

Os módulos independentes de interface estão em `src/modelos/`:

- Previsão mensal SARIMA para casos confirmados, com backtest temporal comparado a um baseline sazonal.
- Preparação de previsão diária para 30 dias, que recusa séries desatualizadas.
- Classificadores experimentais para dengue e hospitalização entre casos confirmados. Hospitalização é apenas um indicador substituto, não uma classificação clínica nem um diagnóstico.

Na última verificação da base disponível, havia 22 meses completos — abaixo dos 24 exigidos pelo treino sazonal — e os dados de início dos sintomas estavam desatualizados para uma previsão diária atual. É necessário atualizar/ampliar os dados antes de usar essas previsões. Todo modelo clínico precisa de validação com dados representativos e revisão por profissionais de saúde; seus resultados não substituem diagnóstico ou decisão clínica.
