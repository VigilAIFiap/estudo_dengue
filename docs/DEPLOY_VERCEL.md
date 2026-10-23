# Publicar o projeto: API, Oracle e front na Vercel

A Vercel hospeda só o **front (Next.js)**. A **API FastAPI roda em outro serviço**, porque usa pandas, scikit-learn e
pmdarima, carrega os dados na inicialização e fala com o Oracle por wallet.

```text
Navegador ──HTTPS──▶ Vercel (Next.js, pasta web/)
                          │  /api/*  (rewrite em web/next.config.ts)
                          ▼
                     API FastAPI em contêiner (Dockerfile na raiz)
                          │  TLS + wallet
                          ▼
                     Oracle Autonomous Database (schema VIGIL_APEX) ── Oracle APEX (revisão)
```

## Ordem recomendada

### 1. Git
- Confirme que `git ls-files web/src/lib` lista os arquivos da `lib` e que `git ls-files wallet` **não** lista nada.
- Confirme que `api/data/municipios.csv`, `Dockerfile`, `requirements-api.txt` e `deploy/entrypoint.py` estão no commit.
- Faça o push.

### 2. Oracle: carregar a camada Prata
A API hospedada lê a tabela `PRATA` (os CSVs do SINAN não vão para o git). Com o schema `VIGIL_APEX` criado e o `.env`
local apontando para ele, na raiz do projeto, com o venv ativo:

```powershell
python src\auditar_fontes.py
python src\read_data_bronze.py
python src\etl.py --batch-size 25000
python src\gerar_gold.py
python src\oracle_upload.py --review-only
python src\oracle_upload.py
```

O último comando carrega as tabelas de staging e confere contagens. Só depois de revisar, substitua `PRATA` e `OURO`
(`python src\oracle_upload.py --mode replace --confirm-replace`). É uma operação destrutiva e confirmada; se as tabelas
de produção ainda estiverem vazias, não há dados a perder. Confira no banco:

```sql
SELECT COUNT(*) FROM PRATA;
```

### 3. API em um serviço com Docker
Em qualquer serviço que construa imagens a partir de um `Dockerfile` (Render, Railway, Fly.io ou uma VM):

- **Build:** o `Dockerfile` da raiz. Ele instala `requirements-api.txt` e inicia `deploy/entrypoint.py`.
- **Porta:** a que o serviço informar na variável `PORT` (o entrypoint já a usa).
- **Verificação de saúde:** caminho `/healthz`.
- **Memória:** reserve pelo menos 1 GB. A API mantém todas as notificações em memória, e a carga inicial do Oracle pode
  levar alguns minutos.
- **Plano que não hiberne:** em planos gratuitos que desligam por inatividade, cada despertar recarrega os dados.

Variáveis de ambiente (todas como segredo do serviço, nunca no repositório):

| Variável | Valor |
| --- | --- |
| `DATA_SOURCE` | `oracle` |
| `ORACLE_API_TABLE` | `PRATA` |
| `DB_USER` | `VIGIL_APEX` |
| `DB_PASSWORD` | senha do usuário no Oracle |
| `DB_DSN` | alias do `tnsnames.ora`, por exemplo o terminado em `_low` |
| `WALLET_PASSWORD` | senha definida ao baixar a wallet |
| `WALLET_ZIP_B64` | o `.zip` da wallet em base64 (comando abaixo) |
| `API_CORS_ORIGINS` | endereço público do front, sem barra no final |
| `TRIAGE_FORM_ENABLED` | `false` em endereço público |
| `VIGIL_DQ_SCHEMA` | `VIGIL_APEX` |
| `DENGUE_MUNICIPIO_BASE` | `residencia` (opcional; padrão `notificacao`) |

Para gerar o valor de `WALLET_ZIP_B64`, no PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\caminho\Wallet_XXXX.zip"))
```

Cole o resultado na variável do serviço. A wallet é extraída apenas dentro do contêiner.

**Rede do banco:** o Autonomous Database aceita conexões com wallet de qualquer lugar por padrão. Se você restringiu por
IP, libere o serviço de hospedagem, cujo IP pode mudar.

**Teste:** `https://URL-DA-API/healthz` deve responder `{"status":"ok"}` e `https://URL-DA-API/api/meta`, com a cobertura
dos dados e `"fonte_dados": "oracle"`.

### 4. Front na Vercel
1. *Add New → Project* e importe o repositório.
2. **Root Directory:** `web`. Mantenha os comandos padrão do Next.js.
3. **Environment Variables** (Production e Preview):
   - `API_URL` = URL pública da API, com `https://` e sem barra no final.
   - `NEXT_PUBLIC_APEX_URL` (opcional) = link da fila no Oracle APEX.
4. *Deploy*.

`API_URL` e `NEXT_PUBLIC_APEX_URL` são lidas **no build**: depois de alterá-las, faça um novo deploy.

### 5. Fechar o ciclo
- Em `API_CORS_ORIGINS`, use o endereço exato do front (e do domínio próprio, se houver), separados por vírgula.
- Abra o site: o topo de cada tela mostra a fonte (SINAN / DATASUS), a base usada e o período analisado.
- Plano gratuito da Vercel (Hobby): uso pessoal e não comercial. Confira os termos em vercel.com/pricing.

## Formulário público

O Acolhimento grava dados de saúde (sem identificação direta) no Oracle, e a API só confere o cabeçalho `Origin`, que
**não é autenticação**. Em um endereço público:

- mantenha `TRIAGE_FORM_ENABLED=false`: a tela abre e explica que o recebimento está desativado;
- ligue o formulário só durante uma demonstração controlada e desligue depois, com dados fictícios;
- para uso real, coloque autenticação na frente do front e da API (veja `docs/GUIA_PUBLICACAO.md`).

## Verificação local antes de publicar

```powershell
python -m unittest discover -s tests -v
cd web
npm ci
npm run typecheck
npm test
npm run build
```
