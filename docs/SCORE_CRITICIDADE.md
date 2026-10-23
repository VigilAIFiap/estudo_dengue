# Score de criticidade municipal: revisão da metodologia

Este documento registra a revisão do score de criticidade (`src/criticidade.py`): o problema encontrado, as decisões tomadas, os parâmetros escolhidos e o efeito da mudança sobre dados reais do SINAN.

> O score é um indicador analítico do projeto para priorização e exploração de dados. Não é classificação clínica nem protocolo oficial de risco epidemiológico.

## 1. Pedido

Revisar como o score é calculado e ajustá-lo para ficar mais próximo da realidade. Um município com poucos casos não deve entrar como Crítico só porque grande parte desses casos foi internada.

## 2. Como o score era calculado

1. Agregação por município notificador (`ID_MUNICIP`): notificações, óbitos (`EVOLUCAO` 2 ou 3) e hospitalizações.
2. Só entram municípios com mais notificações que o 1º quartil do recorte.
3. **Piso de 50 casos:** abaixo de 50 notificações, as taxas de óbito e hospitalização eram zeradas.
4. Normalização min-max (0 a 1) de cada componente entre os municípios do recorte.
5. `score = 100 × (0,5 × volume + 0,3 × taxa de óbito + 0,2 × taxa de hospitalização)`, com volume = log(1 + notificações).
6. Níveis com cortes fixos: Crítico ≥ 50, Alto ≥ 35, Médio ≥ 20, Baixo < 20.

## 3. Problemas encontrados

Os testes usaram os dados abertos do SINAN (`DENGBR25.csv` e `DENGBR26.csv`, 2.104.326 notificações de jan/2025 a out/2026), carregados pelo mesmo `api/dataset.py` que a API usa.

**3.1. Degrau no piso de 50 casos.** Com 49 notificações, o município não pontuava nada em severidade; com 50, passava a usar a taxa bruta inteira. Em 2026, os municípios que mais se beneficiaram estavam exatamente nesse limite:

| Recorte 2026 | Notificações | Internações | Óbitos | Taxa de internação | Score antigo | Posição |
|---|---:|---:|---:|---:|---:|---:|
| Barbalha (CE) | 50 | 31 | 2 | 62% | 56,9 Crítico | **1º do Brasil** |
| Monteiro (PB) | 82 | 30 | 3 | 37% | 51,2 Crítico | 3º |
| Bom Jesus (PI) | 50 | 17 | 2 | 34% | 50,3 Crítico | 4º |

Para comparação, Goiânia teve 35.425 notificações no mesmo período e ficou em 2º.

**3.2. Taxas de poucos casos são muito instáveis.** Com 50 casos, 2 óbitos dão 4% de letalidade, cerca de 30 vezes a média nacional do recorte (0,13%). Um óbito a mais ou a menos muda tudo.

**3.3. Taxa de internação mede também o jeito de notificar.** Municípios pequenos ou polos hospitalares regionais (Barbalha é polo do Cariri) tendem a notificar sobretudo os casos que chegam ao hospital. Isso infla a proporção de internados sem que a epidemia local seja maior.

**3.4. Outliers distorcem a escala min-max.** Como a maior taxa do recorte vira 1, um município minúsculo com taxa extrema comprimia a severidade de todos os outros perto de zero. No período completo, só as 3 maiores cidades do país passavam de 50 pontos.

## 4. Nova metodologia

As etapas 1, 2, 4, 5 e 6 continuam iguais (inclusive pesos e cortes). O piso de 50 casos foi substituído por três mecanismos:

### 4.1. Taxas suavizadas (Bayes empírico)

Cada taxa é puxada para a taxa agregada do recorte, como se o município tivesse *K* notificações extras com a taxa média:

```
taxa_suavizada = (eventos + K × taxa_do_recorte) / (notificações + K)
```

Com poucos casos, o resultado fica perto da média; com muitos, fica perto da taxa observada. É a média posterior de um modelo Beta-Binomial, técnica padrão para comparar taxas de áreas com populações muito diferentes.

| Parâmetro | Valor | Justificativa |
|---|---:|---|
| `PSEUDO_CASOS_OBITO` | 500 | Estimativa por método dos momentos nos dados de 2025–2026 resultou em K entre ~400 e ~1.400, conforme o filtro mínimo de casos. Escolhido um valor no limite inferior, para não apagar sinais reais de municípios médios. |
| `PSEUDO_CASOS_HOSPITALIZACAO` | 100 | A estimativa estatística resultou em K ≈ 6–11, porque a taxa de internação varia muito entre municípios. Essa variação, porém, reflete em boa parte a prática de notificação (item 3.3), e não gravidade. Por isso foi adotado um valor deliberadamente mais conservador. |

Exemplo (Barbalha, recorte 2026): a taxa de óbito cai de 4,0% para 0,45%, e a de internação, de 62% para 25%.

### 4.2. Credibilidade proporcional ao volume

Depois da normalização, os componentes de óbito e de hospitalização são multiplicados por:

```
credibilidade = notificações / (notificações + 100)      # CASOS_CREDIBILIDADE = 100
```

| Notificações | 10 | 50 | 100 | 300 | 1.000 | 10.000 |
|---|---:|---:|---:|---:|---:|---:|
| Peso da severidade | 9% | 33% | 50% | 75% | 91% | 99% |

Isso substitui o piso de 50 casos por uma rampa contínua. A ideia é que severidade agrave a situação de um município com volume relevante, e não que torne crítico, sozinha, um município com poucos casos. Com 49 ou 50 notificações, o resultado agora é praticamente o mesmo (há teste para isso).

O 4.1 trata o **ruído estatístico**, e o 4.2 é uma **decisão de priorização**: com o mesmo nível de severidade, um município com mais casos representa um problema maior.

### 4.3. Trava: Crítico exige ao menos 100 notificações

Se o score passar de 50 mas o município tiver menos de 100 notificações (`MINIMO_CASOS_CRITICO`), o nível fica limitado a **Alto**. Com os mecanismos 4.1 e 4.2, isso não aconteceu em nenhum recorte testado. A trava é uma garantia explícita do requisito, caso os parâmetros sejam alterados no futuro. O painel do município avisa quando ela foi aplicada (`limitado_por_volume`).

### 4.4. Fórmula final

```
volume      = minmax(log(1 + n))
obito       = minmax(taxa_suavizada(óbitos, K=500))         × n/(n+100)
internacao  = minmax(taxa_suavizada(internações, K=100))    × n/(n+100)
score       = 100 × (0,5 × volume + 0,3 × obito + 0,2 × internacao)
nível       = cortes fixos (50 / 35 / 20); Crítico só com n ≥ 100
```

## 5. Decisões mantidas e alternativas descartadas

- **Pesos (50/30/20) e cortes (50/35/20) mantidos.** Já estão documentados no app e validados no Oracle. O problema estava no tratamento das taxas, não nos pesos.
- **Min-max mantido.** Foi testada uma normalização por razão em relação à média do recorte (limitada a 3×). Ela é mais interpretável, mas inflava a escala: 249 municípios Críticos no período completo. Isso exigiria recalibrar os cortes. Com as taxas suavizadas, o min-max deixa de ser dominado por outliers.
- **Só suavização, sem credibilidade:** não resolve sozinha. Barbalha continuava Crítico no recorte do Ceará (63 pontos), porque 31 internações em 50 casos ainda é extremo mesmo depois de suavizado.
- **Só a trava de 100 casos, sem suavização:** cria outro degrau (99 contra 100 casos) e não corrige a distorção da escala min-max.

Resumo das variantes testadas (Críticos com menos de 200 notificações, somando os recortes avaliados): antiga 8; só suavização 9; suavização + trava 5; **suavização + credibilidade + trava (adotada) 0**.

## 6. Resultados: antes e depois

Gerados com os dados abertos do SINAN (DENGBR25 e DENGBR26, baixados em 23/10/2026) e `municipios.csv`.

### Todo o período (jan/2025–out/2026)

3777 municípios pontuados (corte do 1º quartil: mais de 10 notificações).

| Nível | Antes | Depois |
|---|---:|---:|
| Crítico | 3 | 24 |
| Alto | 89 | 188 |
| Médio | 854 | 971 |
| Baixo | 2831 | 2594 |
| **Críticos com menos de 200 notificações** | **0** | **0** |
| Mediana de notificações dos Críticos | 68.771 | 8.690 |

Top 10 depois da mudança:

| # | Município | Notificações | Internações | Óbitos | Score antes (posição) | Score depois | Nível depois |
|---:|---|---:|---:|---:|---|---:|---|
| 1 | Americana (SP) | 10.830 | 768 | 51 | 42.5 (19º) | 57.9 | Crítico |
| 2 | Goiânia (GO) | 68.771 | 3.736 | 116 | 51.1 (2º) | 57.3 | Crítico |
| 3 | São José do Rio Preto (SP) | 67.777 | 3.969 | 107 | 51.1 (3º) | 57.0 | Crítico |
| 4 | Maringá (PR) | 5.704 | 837 | 27 | 40.8 (29º) | 57.0 | Crítico |
| 5 | São Paulo (SP) | 83.095 | 3.961 | 85 | 51.7 (1º) | 55.6 | Crítico |
| 6 | Patos de Minas (MG) | 1.642 | 236 | 13 | 35.2 (90º) | 55.4 | Crítico |
| 7 | Marília (SP) | 15.210 | 856 | 54 | 43.5 (12º) | 55.3 | Crítico |
| 8 | São Luís (MA) | 5.265 | 1.561 | 12 | 42.8 (16º) | 54.9 | Crítico |
| 9 | Sobral (CE) | 2.988 | 1.010 | 8 | 40.8 (30º) | 54.0 | Crítico |
| 10 | Uberlândia (MG) | 35.407 | 2.606 | 54 | 47.7 (6º) | 53.8 | Crítico |

Entraram no nível Crítico: Campinas (SP, 54.140 notif., 49.3 → 53.1); Porto Alegre (RS, 59.861 notif., 48.8 → 51.1); Uberlândia (MG, 35.407 notif., 47.7 → 53.8); Ribeirão Preto (SP, 24.087 notif., 45.3 → 51.5); Marília (SP, 15.210 notif., 43.5 → 55.3); Recife (PE, 13.192 notif., 43.4 → 50.1); Sorocaba (SP, 15.160 notif., 43.1 → 51.4); São Luís (MA, 5.265 notif., 42.8 → 54.9); Londrina (PR, 9.326 notif., 42.6 → 53.6); Americana (SP, 10.830 notif., 42.5 → 57.9); Salvador (BA, 8.053 notif., 41.8 → 52.1); Maringá (PR, 5.704 notif., 40.8 → 57.0); Sobral (CE, 2.988 notif., 40.8 → 54.0); Uberaba (MG, 6.356 notif., 39.4 → 53.5); Limeira (SP, 7.054 notif., 39.2 → 51.4); Fortaleza (CE, 2.461 notif., 38.7 → 53.7); Salto (SP, 3.619 notif., 36.0 → 52.3); Itapevi (SP, 1.780 notif., 35.7 → 51.0); Patos de Minas (MG, 1.642 notif., 35.2 → 55.4); Santarém (PA, 1.337 notif., 34.1 → 52.2); Lins (SP, 1.603 notif., 33.6 → 50.7)

### 2026

3058 municípios pontuados (corte do 1º quartil: mais de 4 notificações).

| Nível | Antes | Depois |
|---|---:|---:|
| Crítico | 4 | 8 |
| Alto | 58 | 93 |
| Médio | 458 | 493 |
| Baixo | 2538 | 2464 |
| **Críticos com menos de 200 notificações** | **3** | **0** |
| Mediana de notificações dos Críticos | 66 | 3.234 |

Top 10 depois da mudança:

| # | Município | Notificações | Internações | Óbitos | Score antes (posição) | Score depois | Nível depois |
|---:|---|---:|---:|---:|---|---:|---|
| 1 | Sobral (CE) | 2.950 | 990 | 8 | 45.6 (6º) | 60.1 | Crítico |
| 2 | Goiânia (GO) | 35.425 | 1.611 | 56 | 52.3 (2º) | 58.8 | Crítico |
| 3 | Santarém (PA) | 1.128 | 156 | 8 | 38.7 (27º) | 57.2 | Crítico |
| 4 | Fortaleza (CE) | 1.878 | 473 | 7 | 41.8 (15º) | 56.6 | Crítico |
| 5 | Salvador (BA) | 4.279 | 733 | 12 | 44.0 (10º) | 56.4 | Crítico |
| 6 | São Luís (MA) | 3.517 | 1.109 | 5 | 45.2 (7º) | 55.5 | Crítico |
| 7 | Recife (PE) | 5.762 | 732 | 9 | 43.7 (12º) | 51.4 | Crítico |
| 8 | Barra do Garças (MT) | 1.031 | 162 | 5 | 37.0 (40º) | 50.3 | Crítico |
| 9 | Taubaté (SP) | 4.650 | 204 | 11 | 41.1 (19º) | 49.9 | Alto |
| 10 | Dracena (SP) | 808 | 100 | 5 | 35.8 (51º) | 49.7 | Alto |

Saíram do nível Crítico:

| Município | Notificações | Internações | Óbitos | Antes | Depois |
|---|---:|---:|---:|---|---|
| Barbalha (CE) | 50 | 31 | 2 | 56.9 Crítico (1º) | 22.8 Médio (441º) |
| Bom Jesus (PI) | 50 | 17 | 2 | 50.3 Crítico (4º) | 21.4 Médio (507º) |
| Monteiro (PB) | 82 | 30 | 3 | 51.2 Crítico (3º) | 31.4 Médio (156º) |

Entraram no nível Crítico: Sobral (CE, 2.950 notif., 45.6 → 60.1); São Luís (MA, 3.517 notif., 45.2 → 55.5); Salvador (BA, 4.279 notif., 44.0 → 56.4); Recife (PE, 5.762 notif., 43.7 → 51.4); Fortaleza (CE, 1.878 notif., 41.8 → 56.6); Santarém (PA, 1.128 notif., 38.7 → 57.2); Barra do Garças (MT, 1.031 notif., 37.0 → 50.3)

### SP, 2026

420 municípios pontuados (corte do 1º quartil: mais de 4 notificações).

| Nível | Antes | Depois |
|---|---:|---:|
| Crítico | 4 | 9 |
| Alto | 21 | 23 |
| Médio | 76 | 86 |
| Baixo | 319 | 302 |
| **Críticos com menos de 200 notificações** | **1** | **0** |
| Mediana de notificações dos Críticos | 5.480 | 1.673 |

Top 10 depois da mudança:

| # | Município | Notificações | Internações | Óbitos | Score antes (posição) | Score depois | Nível depois |
|---:|---|---:|---:|---:|---|---:|---|
| 1 | Dracena (SP) | 808 | 100 | 5 | 49.5 (5º) | 73.9 | Crítico |
| 2 | Taubaté (SP) | 4.650 | 204 | 11 | 50.5 (3º) | 65.1 | Crítico |
| 3 | São Paulo (SP) | 10.986 | 625 | 7 | 55.1 (1º) | 61.8 | Crítico |
| 4 | Ribeirão Preto (SP) | 874 | 83 | 3 | 44.5 (9º) | 60.5 | Crítico |
| 5 | São José dos Campos (SP) | 1.673 | 121 | 4 | 45.9 (7º) | 60.3 | Crítico |
| 6 | São José do Rio Preto (SP) | 6.310 | 266 | 4 | 50.3 (4º) | 55.9 | Crítico |
| 7 | Tremembé (SP) | 490 | 12 | 3 | 38.5 (17º) | 52.5 | Crítico |
| 8 | Santos (SP) | 935 | 96 | 1 | 42.8 (11º) | 52.4 | Crítico |
| 9 | Jacareí (SP) | 2.471 | 81 | 3 | 44.0 (10º) | 51.6 | Crítico |
| 10 | Barretos (SP) | 298 | 24 | 2 | 40.2 (14º) | 49.7 | Alto |

Saíram do nível Crítico:

| Município | Notificações | Internações | Óbitos | Antes | Depois |
|---|---:|---:|---:|---|---|
| Sertãozinho (SP) | 79 | 7 | 2 | 54.0 Crítico (2º) | 34.4 Médio (34º) |

Entraram no nível Crítico: Dracena (SP, 808 notif., 49.5 → 73.9); São José dos Campos (SP, 1.673 notif., 45.9 → 60.3); Ribeirão Preto (SP, 874 notif., 44.5 → 60.5); Jacareí (SP, 2.471 notif., 44.0 → 51.6); Santos (SP, 935 notif., 42.8 → 52.4); Tremembé (SP, 490 notif., 38.5 → 52.5)

### CE, 2026

129 municípios pontuados (corte do 1º quartil: mais de 6 notificações).

| Nível | Antes | Depois |
|---|---:|---:|
| Crítico | 3 | 3 |
| Alto | 10 | 14 |
| Médio | 32 | 32 |
| Baixo | 84 | 80 |
| **Críticos com menos de 200 notificações** | **1** | **0** |
| Mediana de notificações dos Críticos | 1.878 | 1.878 |

Top 10 depois da mudança:

| # | Município | Notificações | Internações | Óbitos | Score antes (posição) | Score depois | Nível depois |
|---:|---|---:|---:|---:|---|---:|---|
| 1 | Sobral (CE) | 2.950 | 990 | 8 | 62.9 (2º) | 81.4 | Crítico |
| 2 | Fortaleza (CE) | 1.878 | 473 | 7 | 57.1 (3º) | 76.5 | Crítico |
| 3 | Tabuleiro do Norte (CE) | 755 | 13 | 4 | 43.0 (5º) | 57.3 | Crítico |
| 4 | Tianguá (CE) | 1.315 | 36 | 2 | 45.2 (4º) | 48.8 | Alto |
| 5 | Limoeiro do Norte (CE) | 380 | 76 | 1 | 41.1 (6º) | 48.2 | Alto |
| 6 | Juazeiro do Norte (CE) | 523 | 76 | 0 | 40.1 (7º) | 42.2 | Alto |
| 7 | Várzea Alegre (CE) | 395 | 77 | 0 | 39.3 (8º) | 42.2 | Alto |
| 8 | Jaguaribara (CE) | 433 | 10 | 1 | 36.3 (11º) | 41.3 | Alto |
| 9 | Crato (CE) | 316 | 64 | 0 | 37.7 (10º) | 40.4 | Alto |
| 10 | Jardim (CE) | 267 | 17 | 1 | 34.6 (14º) | 40.4 | Alto |

Saíram do nível Crítico:

| Município | Notificações | Internações | Óbitos | Antes | Depois |
|---|---:|---:|---:|---|---|
| Barbalha (CE) | 50 | 31 | 2 | 65.7 Crítico (1º) | 31.5 Médio (26º) |

Entraram no nível Crítico: Tabuleiro do Norte (CE, 755 notif., 43.0 → 57.3)

### Setembro/2026 em diante

1435 municípios pontuados (corte do 1º quartil: mais de 1 notificações).

| Nível | Antes | Depois |
|---|---:|---:|
| Crítico | 5 | 4 |
| Alto | 37 | 34 |
| Médio | 109 | 144 |
| Baixo | 1284 | 1253 |
| **Críticos com menos de 200 notificações** | **3** | **0** |
| Mediana de notificações dos Críticos | 157 | 725 |

Top 10 depois da mudança:

| # | Município | Notificações | Internações | Óbitos | Score antes (posição) | Score depois | Nível depois |
|---:|---|---:|---:|---:|---|---:|---|
| 1 | Recife (PE) | 808 | 76 | 2 | 55.2 (2º) | 69.1 | Crítico |
| 2 | Goiânia (GO) | 1.881 | 59 | 0 | 51.9 (4º) | 51.6 | Crítico |
| 3 | Salvador (BA) | 642 | 89 | 0 | 49.9 (6º) | 51.5 | Crítico |
| 4 | Ribeirão Preto (SP) | 262 | 8 | 1 | 46.0 (10º) | 50.5 | Crítico |
| 5 | Tabuleiro do Norte (CE) | 256 | 3 | 1 | 45.0 (16º) | 49.4 | Alto |
| 6 | Mossoró (RN) | 416 | 59 | 0 | 46.7 (8º) | 47.6 | Alto |
| 7 | Feira de Santana (BA) | 138 | 15 | 1 | 54.3 (3º) | 47.4 | Alto |
| 8 | Brasília (DF) | 587 | 46 | 0 | 45.6 (13º) | 46.6 | Alto |
| 9 | São Paulo (SP) | 488 | 46 | 0 | 45.1 (15º) | 46.1 | Alto |
| 10 | Aparecida de Goiânia (GO) | 981 | 17 | 0 | 46.0 (9º) | 45.9 | Alto |

Saíram do nível Crítico:

| Município | Notificações | Internações | Óbitos | Antes | Depois |
|---|---:|---:|---:|---|---|
| Belém (PA) | 83 | 14 | 1 | 65.9 Crítico (1º) | 41.5 Alto (21º) |
| Feira de Santana (BA) | 138 | 15 | 1 | 54.3 Crítico (3º) | 47.4 Alto (7º) |
| Sobral (CE) | 157 | 53 | 0 | 50.8 Crítico (5º) | 44.2 Alto (14º) |

Entraram no nível Crítico: Salvador (BA, 642 notif., 49.9 → 51.5); Ribeirão Preto (SP, 262 notif., 46.0 → 50.5)

### 6.1. Leitura dos resultados

- **Objetivo atingido:** em nenhum recorte há município Crítico com menos de 200 notificações. Antes eram 3 em 2026 e em set/2026 (Barbalha, Bom Jesus, Monteiro, Belém, Feira de Santana, Sobral).
- **Os municípios pequenos não somem:** Barbalha, por exemplo, cai para Médio, ainda acima da maioria dos municípios.
- **Mais Críticos no período completo (3 → 24):** é efeito da correção do item 3.4. Sem os outliers comprimindo a escala, cidades médias e grandes com taxas de fato altas (Maringá, Londrina, Sobral, São Luís, Campinas, Ribeirão Preto) voltam a pontuar em severidade. Antes, só as 3 cidades com mais notificações do país passavam de 50. 24 de 3.777 municípios pontuados equivale a 0,6%.
- **O score continua relativo ao recorte:** mudar período, UF ou classificação muda os valores, como já acontecia.

## 7. Limitações e próximos passos recomendados

1. **Usar população (incidência por 100 mil habitantes).** Esta é a principal limitação que continua. O componente de volume usa notificações absolutas, o que favorece cidades grandes. A medida oficial do Ministério da Saúde é a incidência por 100 mil habitantes (≥ 300 é considerada alta). O `municipios.csv` atual não tem população. A sugestão é incluir as estimativas do IBGE (tabela SIDRA 6579) e trocar `log(1 + casos)` pela incidência suavizada.
2. **Definição de óbito.** O score conta `EVOLUCAO` 2 (óbito por dengue) **e 3 (óbito por outras causas)**, por regra herdada do painel original. Para medir gravidade da dengue, o correto seria só `EVOLUCAO = 2` (a coluna `obito_dengue` já existe). Isso não foi alterado aqui por ser uma regra de negócio declarada no código; vale o grupo decidir.
3. **Município notificador ou de residência.** O score agrega por `ID_MUNICIP` (onde o caso foi notificado). Polos hospitalares recebem casos de cidades vizinhas. `ID_MN_RESI` (residência) refletiria melhor onde está a transmissão.
4. **Calibração dos parâmetros.** K = 500, K = 100 e credibilidade = 100 foram escolhidos a partir dos dados de 2025–2026 e por julgamento. Com mais anos de dados, vale reestimar.

## 8. Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `src/criticidade.py` | Novos parâmetros, suavização, credibilidade e trava; piso de 50 casos removido. |
| `api/analytics.py` | Expõe os novos parâmetros na metodologia e no detalhe do município. |
| `api/schemas.py` | `Metodologia`: `piso_casos` dá lugar a `pseudo_casos_obito`, `pseudo_casos_hospitalizacao`, `casos_credibilidade` e `minimo_casos_critico`. `Componentes`: `abaixo_piso` dá lugar a `credibilidade` e `limitado_por_volume`. |
| `web/src/components/municipios/methodology.tsx`, `web/src/app/page.tsx`, `web/src/components/municipios/municipio-drawer.tsx` | Textos de metodologia e avisos do painel do município. |
| `tests/test_api.py` | Testes do novo comportamento: caso Barbalha, ausência de degrau e trava do nível Crítico. |

**Atenção para o frontend:** a pasta `web/src/lib/` (tipos gerados da API, formatação, consultas) não está no repositório, porque a regra `lib/` do `.gitignore` da raiz a ignora. Quem tem a pasta localmente precisa: (1) regenerar os tipos com `npm run gen:api` com a API rodando, para os novos campos aparecerem em `Schemas`; e (2) corrigir o `.gitignore` (trocar `lib/` por `/lib/`) e versionar `web/src/lib/`, senão o site não compila a partir de um clone novo.

## 9. Como reproduzir

```powershell
python -m unittest discover -s tests -v
```

Para refazer o comparativo, baixe `DENGBR25.csv.zip` e `DENGBR26.csv.zip` do OpenDataSUS (SINAN – Dengue), coloque os CSVs e o `municipios.csv` em `dados/raw/` (`DENGBR23.csv` e `DENGBR24.csv` podem conter só o cabeçalho), carregue com `api.dataset.carregar` e chame `criticality_from_notifications` da versão anterior (`git show <commit-anterior>:src/criticidade.py`) e da atual sobre o mesmo recorte.
