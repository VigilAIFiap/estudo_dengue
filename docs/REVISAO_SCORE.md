# Revisão do score de criticidade

Análise feita sobre as notificações do SINAN de 29/12/2024 a 10/05/2026 (1.956.511 registros, 5.031 municípios;
3.728 pontuados depois do corte no 1º quartil, que é de 8 notificações).

## O que estava estranho

| Verificação | Resultado antes |
| --- | --- |
| Peso efetivo de cada parte (correlação de postos com o score) | volume 0,98 · taxa de óbito 0,58 · taxa de hospitalização 0,77 |
| Contribuição média ao score | volume 12,4 pontos · óbito 0,35 · hospitalização 0,8 |
| Níveis | Crítico 3 · Alto 89 · Médio 862 · Baixo 2.774 |

1. **O score era, na prática, só volume.** Os pesos nominais eram 50/30/20, mas a normalização min-max das taxas era
   dominada por um único município atípico (taxa de óbito máxima de 6,45%): todos os outros ficavam com taxa
   normalizada perto de zero (mediana 0).
2. **Poucos casos viravam "Alto" por acaso.** O município 353620 (62 notificações, 4 óbitos) ficava em 11º lugar, acima de
   cidades com dezenas de milhares de casos, porque a taxa 4/62 definia o máximo da escala.
3. **Regra de óbito diferente dos indicadores.** O score contava evolução 2 ou 3 (inclui morte por outras causas), e os
   indicadores contam só a 2 (óbito pelo agravo).

## Fórmula nova

```text
score = 100 × fator_de_volume × severidade
```

- **fator_de_volume:** log das notificações, de 0 a 1 entre os municípios do recorte. O número de casos multiplica a severidade.
- **severidade:** 60% do percentil da taxa de óbito + 40% do percentil da taxa de hospitalização.
- **taxas suavizadas:** cada taxa é puxada para a taxa geral do recorte, com peso de 50 casos. Isso substitui o antigo piso de 50 casos.
- **óbito:** evolução 2 (óbito pelo agravo), igual aos indicadores.
- **cortes:** mantidos (Crítico ≥ 50, Alto ≥ 35, Médio ≥ 20).

## Resultado

| Verificação | Antes | Depois |
| --- | --- | --- |
| Peso efetivo do volume / da severidade | 0,98 / ~0,6 a 0,8 (óbito e hospitalização separados) | 0,60 / 0,12 |
| Crítico / Alto / Médio / Baixo | 3 / 89 / 862 / 2.774 | 73 / 150 / 274 / 3.231 |
| Município 353620 (62 casos, 4 óbitos) | 11º, nível Alto | 500º, nível Baixo |
| Críticos: casos mínimo / mediana | 56.633 / 66.642 | 1.248 / 4.494 |
| Alto ou Crítico com menos de 1.000 casos | 5 | 78 |

Interpretação: a severidade agora pesa de fato, o município atípico deixou de distorcer a escala e os níveis se distribuem melhor.
Municípios de porte médio (centenas a poucos milhares de casos) com taxas muito acima dos demais chegam a Alto, o que é intencional.

## Limites conhecidos

- A severidade é **relativa** (percentis entre os municípios do recorte): sempre haverá municípios no topo, mesmo que as taxas absolutas sejam baixas.
- Não há população nos dados: o fator de volume é absoluto e não é incidência por habitante.
- Os cortes (50, 35, 20) são escolha de projeto. Com a fórmula nova, ~2% dos municípios pontuados ficam em Crítico e ~4% em Alto; ajuste os cortes se quiser outra proporção.
- A taxa de hospitalização depende do preenchimento do campo HOSPITALIZ, que tem muitos vazios nas notificações.
- Alternativa não aplicada: incluir a proporção de casos com sinais de alarme ou graves (classificação 11 e 12) como terceira parte da severidade.

## Municípios em branco no mapa

O arquivo `municipios.csv` está completo (5.571 municípios, sem valores vazios nem códigos repetidos, com os municípios criados
depois de 2013 e todos os códigos das notificações). Os brancos vêm dos dados:

| Situação | Municípios | Como aparece |
| --- | --- | --- |
| Sem nenhuma notificação no período | 540 (9,7% do cadastro) | "Sem notificação" |
| Com 1 a 8 notificações (até o 1º quartil) | 1.303 (23,4%) | "Sem score" (cinza) |

A base usa o **município de notificação** (`ID_MUNICIP`), onde fica a unidade de saúde, e não o de residência (`ID_MN_RESI`).
Cidades pequenas sem unidade notificadora aparecem vizinhas. Os municípios sem notificação se concentram no RS (151 de 497),
SC (64), PB (56), PI (50) e SE (27). A legenda do mapa agora mostra a contagem de cada grupo e essa explicação.
Para reduzir os vazios, a API aceita usar o município de residência: defina `DENGUE_MUNICIPIO_BASE=residencia` e reinicie. Isso
exige a coluna `ID_MN_RESI` em todos os arquivos (ou na tabela PRATA). Notificações sem residência válida no cadastro usam o município
de notificação e são contadas em `sem_residencia` (`GET /api/meta`). Os números e os rankings mudam, porque os casos passam a ser
contados onde o paciente mora.
