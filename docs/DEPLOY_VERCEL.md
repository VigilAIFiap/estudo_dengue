# Publicar o front na Vercel

A Vercel hospeda o **front (Next.js)**. A **API FastAPI não roda na Vercel**: ela usa pandas, scikit-learn e pmdarima,
carrega os dados na inicialização e fala com o Oracle por wallet. Ela precisa de outro serviço.

```text
Navegador ──HTTPS──▶ Vercel (Next.js, pasta web/)
                          │  /api/*  (rewrite definido em web/next.config.ts)
                          ▼
                     API FastAPI  (Render, Railway, Fly.io ou VM)
                          │  TLS + wallet
                          ▼
                     Oracle Database ── Oracle APEX (revisão)
```

## Antes de começar

1. **A pasta `web/src/lib` precisa estar no git.** A regra `lib/` do `.gitignore` a escondia; a versão corrigida usa
   `/lib/`. Confirme com `git ls-files web/src/lib` (deve listar 9 arquivos). Sem isso o build falha com
   "Module not found: @/lib/api".
2. **Plano gratuito da Vercel (Hobby):** é restrito a uso pessoal e não comercial. Serve para portfólio e entrega
   acadêmica. Confira os termos em vercel.com/pricing.
3. **A API precisa estar no ar antes**, para você ter a URL dela.

## 1. Publicar a API (resumo)

Em qualquer serviço que rode Python:

- Build: `pip install -r requirements.txt`
- Start: `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT` (use a porta que o serviço fornecer)
- Variáveis (como segredos do serviço, nunca no repositório):

```dotenv
DATA_SOURCE=csv            # ou oracle
API_CORS_ORIGINS=https://SEU-PROJETO.vercel.app
TRIAGE_FORM_ENABLED=false  # veja "Formulário público" abaixo
VIGIL_DQ_SCHEMA=VIGIL_APEX
```

**De onde a API lê os dados.** Os CSVs do SINAN estão no `.gitignore`, então **não chegam ao serviço pelo git**. Escolha:

- `DATA_SOURCE=oracle` com a tabela `PRATA` carregada (`ORACLE_API_TABLE=PRATA`). Exige `DB_USER`, `DB_PASSWORD`,
  `DB_DSN`, `WALLET_PASSWORD` e a wallet como arquivo secreto, com `WALLET_DIR` apontando para ela. O banco precisa
  aceitar conexões vindas do serviço (regras de rede do Autonomous Database).
- `DATA_SOURCE=csv` com os arquivos levados ao serviço por disco persistente ou upload, em `dados/raw/` ou no caminho de
  `DENGUE_DATA_DIR`.

Teste: `https://URL-DA-API/api/meta` deve responder com a cobertura dos dados.

## 2. Publicar o front na Vercel

1. *Add New → Project* e importe o repositório do GitHub.
2. **Root Directory:** `web`. O framework (Next.js) é detectado sozinho; mantenha os comandos padrão.
3. **Environment Variables** (Production e Preview):
   - `API_URL` = URL pública da API, com `https://` e sem barra no final.
   - `NEXT_PUBLIC_APEX_URL` (opcional) = link da fila no Oracle APEX.
4. *Deploy*.

O Next.js repassa `/api/*` à API pelo rewrite de `web/next.config.ts`; o navegador só enxerga o domínio da Vercel.
`API_URL` e `NEXT_PUBLIC_APEX_URL` são lidas **no build**: depois de alterá-las, faça um novo deploy.

## 3. Fechar o ciclo

- Coloque na API, em `API_CORS_ORIGINS`, o endereço exato da Vercel (e do domínio próprio, se houver), separados por
  vírgula, sem barra final. O formulário de acolhimento só é aceito de origens listadas ali.
- Abra `https://SEU-PROJETO.vercel.app`: o topo de cada tela mostra a fonte (SINAN / DATASUS) e o período analisado.

## Formulário público

O Acolhimento grava dados de saúde (sem identificação direta) no Oracle, e a API só confere o cabeçalho `Origin`,
que **não é autenticação**. Em um endereço público:

- mantenha `TRIAGE_FORM_ENABLED=false`. A tela continua abrindo e explica que o recebimento está desativado;
- ligue o formulário só durante uma demonstração controlada e desligue depois, com dados fictícios;
- para uso real, coloque autenticação na frente do front e da API (veja `docs/GUIA_PUBLICACAO.md`).

## Verificação

```powershell
cd web
npm ci
npm run typecheck
npm test
npm run build
```

Se o `build` passar localmente, o da Vercel deve passar também.
