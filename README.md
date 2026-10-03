# VigilIA - Painel de Vigilancia Epidemiologica da Dengue

Painel interativo para analise epidemiologica de dengue no Brasil, com previsao de casos, classificacao de risco e gestao de recursos.

## Funcionalidades

### Painel Completo
- Previsao diaria (1-30 dias) e mensal (12 meses) com decomposicao sazonal
- Analise de criticidade: graves, moderados, leves e hospitalizados
- Mapa geografico de municipios com casos e obitos
- Grafico de casos por estado (UF)
- Top 10 municipios com maior incidencia

### Avaliacao de Paciente
- Classificacao de risco (ALTO / MEDIO / BAIXO) baseada em idade, sintomas, comorbidades e sinais de alarme
- Conduta recomendada conforme protocolo clinico

### Gestao de Recursos
- Projecao de leitos (enfermaria e UTI), kits sorologia e fluidos intravenosos
- Ranking de municipios mais criticos com planos de acao
- Recomendacoes de vigilancia e prevencao

## Dados

Fonte: Sistema SINAN/DENGBR (Ministerio da Saude)

| Arquivo | Descricao | Periodo |
|---------|-----------|---------|
| `dados/DENGBR25.csv` | Notificacoes de dengue 2025 | Dez/2024 - Dez/2025 |
| `dados/DENGBR26.csv` | Notificacoes de dengue 2026 | Jan/2026 - Set/2026 |
| `dados/municipios.csv` | Cadastro de municipios com geolocalizacao | IBGE |

## Instalacao

```bash
pip install streamlit pandas numpy plotly statsmodels
```

## Execucao

```bash
streamlit run main.py
```

O painel abre em `http://localhost:8501`.

## Modelos de Previsao

- **Diaria**: Decomposicao sazonal por mês + tendencia linear
- **Mensal**: Decomposicao sazonal com pesos (meses completos recebem maior peso)
- Meses com dados incompletos sao identificados automaticamente e recebem peso reduzido

## Tecnologias

- **Streamlit** - Interface web
- **Plotly** - Graficos interativos
- **Pandas / NumPy** - Manipulacao de dados
- **Statsmodels (SARIMAX)** - Modelagem de series temporais

## Estrutura

```
VigilIA/
├── main.py           # Dashboard principal
├── dados/
│   ├── DENGBR25.csv
│   ├── DENGBR26.csv
│   └── municipios.csv
├── .gitignore
└── README.md
```
