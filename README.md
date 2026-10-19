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

   A API usa os CSVs em `dados/raw/` (ou no diretório configurado em `DENGUE_DATA_DIR`). Para o Vigil Assist, preencha `ANTHROPIC_API_KEY`. A API analítica lê os arquivos locais e **não acessa o Oracle**.

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

A API usa `DATA_SOURCE=csv` por padrão e carrega `DENGBR23.csv` a `DENGBR26.csv` e `municipios.csv` de `dados/raw/` uma vez ao iniciar. Cada CSV anual é filtrado por `NU_ANO` para evitar misturar anos: a auditoria encontrou 1.645.276 notificações de 2023 e 6.564.163 de 2024 nas fontes locais. As cópias Oracle/Parquet antigas tinham apenas 87.996 registros de 2023 e 988.171 de 2024; portanto, `DATA_SOURCE=oracle` não deve ser usado para análises até que a Prata Oracle seja recarregada e validada. O modo CSV descarta notificações inválidas ou futuras e mantém o conjunto em memória. O diretório local pode ser alterado com `DENGUE_DATA_DIR`. Carregar milhões de notificações pode demorar e exigir memória adicional; reiniciar a API executa uma nova leitura. As credenciais Oracle permanecem exclusivamente no `.env` do backend. O navegador continua acessando apenas a API FastAPI. As fontes incluem [SINAN/DATASUS](http://www2.datasus.gov.br/DATASUS/index.php), [INMET](https://portal.inmet.gov.br/) e [CPTEC/INPE](https://www.cptec.inpe.br/).

Quando a Prata Oracle for recarregada e sua cobertura anual for validada, a API também pode usar Oracle. Configure `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_DIR` e `WALLET_PASSWORD` no `.env`, confirme que `PRATA` está carregada e íntegra, e altere:

```dotenv
DATA_SOURCE=oracle
ORACLE_API_TABLE=PRATA
```

Em seguida, inicie a API normalmente. A conexão ocorre no backend ao iniciar; se a conexão/tabela falhar, a API não inicia com dados incompletos. Para voltar aos CSVs locais, configure `DATA_SOURCE=csv` e reinicie.

## Camadas Prata e Ouro no Oracle

Os Parquets `dados/processed/df_prata.parquet` e `dados/processed/df_ouro.parquet` podem ser carregados nas tabelas Oracle `PRATA` e `OURO`. O DDL está em `sql/create_prata_ouro.sql`; execute-o no schema desejado antes da primeira carga. Se `PRATA` já existir, execute também `sql/migrate_prata_nduplic.sql` antes de carregar a nova camada, para incluir a coluna `NDUPLIC_N`. As credenciais Oracle são usadas pelos scripts de ETL/carga e, opcionalmente, pela API quando `DATA_SOURCE=oracle`.

Configure `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_DIR` e `WALLET_PASSWORD` no `.env`. Nunca publique o wallet ou credenciais.

Os dados e arquivos wallet diferentes que estavam na cópia antiga foram preservados localmente em `dados_wallet_pendente_validacao/`. Essa pasta é ignorada pelo Git; compare os arquivos antes de decidir se alguma versão pode ser removida.

```powershell
python src\read_data_bronze.py
python src\etl.py
python src\gerar_gold.py
python src\oracle_upload.py --review-only
python src\oracle_upload.py
```

`read_data_bronze.py` usa `dados/raw/DENGBR23.csv` e `DENGBR24.csv` para 2023 e 2024, filtrando cada arquivo por `NU_ANO`, e consulta `DENGBR25` e `DENGBR26` no Oracle. A escolha evita as fontes Oracle incompletas de 2023 e 2024. O leitor processa os CSVs em blocos e salva as quatro fontes em Parquet; o ETL local gera a Prata e preserva as linhas sinalizadas em `NDUPLIC_N`. A Ouro ignora registros com `NDUPLIC_N=2` e notificações inválidas ou futuras. Datas com relações fora do esperado são reportadas na revisão, sem exclusão automática. A carga ao Oracle substitui os dados de ambas as tabelas usando `DELETE`; em caso de erro, executa rollback, mas pode exceder o espaço de undo para volumes grandes. O script não cria as tabelas nem usa `TRUNCATE`. Valide os Parquets e execute `oracle_upload.py --review-only` antes de qualquer carga; não tente recarregar as tabelas Oracle sem uma estratégia de espaço/undo adequada.

## Modelos preditivos

Os módulos independentes de interface estão em `src/modelos/`:

- Previsão mensal SARIMA para casos confirmados, com backtest temporal comparado a um baseline sazonal.
- Preparação de previsão diária para 30 dias, que recusa séries desatualizadas.
- Classificadores experimentais para dengue e hospitalização entre casos confirmados. Hospitalização é apenas um indicador substituto, não uma classificação clínica nem um diagnóstico.

Na última verificação da base disponível, havia 22 meses completos — abaixo dos 24 exigidos pelo treino sazonal — e os dados de início dos sintomas estavam desatualizados para uma previsão diária atual. É necessário atualizar/ampliar os dados antes de usar essas previsões. Todo modelo clínico precisa de validação com dados representativos e revisão por profissionais de saúde; seus resultados não substituem diagnóstico ou decisão clínica.
