"""Score municipal de criticidade compartilhado pelos serviços analíticos.

Metodologia completa e justificativas: docs/SCORE_CRITICIDADE.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PESO_VOLUME = 0.5
PESO_OBITO = 0.3
PESO_HOSPITALIZACAO = 0.2
CORTES = (("Crítico", 50), ("Alto", 35), ("Médio", 20), ("Baixo", float("-inf")))

# Suavização bayesiana empírica: cada taxa é puxada para a taxa do recorte como se o
# município tivesse K notificações "a mais" com a taxa média. Óbito é raro e ruidoso
# (K estimado entre ~400 e ~1.400 nos dados SINAN 2025-2026); hospitalização depende
# muito de como o município notifica, então usamos K maior que o estimado (~6-11).
PSEUDO_CASOS_OBITO = 500
PSEUDO_CASOS_HOSPITALIZACAO = 100

# Credibilidade da severidade: os componentes de óbito e hospitalização são
# multiplicados por n / (n + CASOS_CREDIBILIDADE). Com 100 casos valem metade;
# com 1.000, ~91%. Substitui o antigo piso de 50 casos (degrau de zero para tudo).
CASOS_CREDIBILIDADE = 100

# Trava final: abaixo deste volume o município não é classificado como Crítico.
MINIMO_CASOS_CRITICO = 100


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por município para o score de criticidade."""
    g = df.groupby("ID_MUNICIP").agg(
        casos=("ID_MUNICIP", "size"),
        obitos=("obito", "sum"),
        hospitalizados=("hospitalizado", "sum"),
        UF=("UF", "first"),
    )
    g["taxa_hospitalizacao"] = np.where(g["casos"] > 0, g["hospitalizados"] / g["casos"], 0)
    g["taxa_obito"] = np.where(g["casos"] > 0, g["obitos"] / g["casos"], 0)
    g = g.reset_index().rename(columns={"ID_MUNICIP": "id_municip"})
    return g


def classificar(s: float) -> str:
    for nivel, corte in CORTES:
        if s >= corte:
            return nivel
    raise ValueError(f"Score inválido: {s}")


def _min_max(s: pd.Series) -> pd.Series:
    return (s - s.min()) / (s.max() - s.min() + 1e-9)


def taxa_suavizada(eventos: pd.Series, casos: pd.Series, pseudo_casos: float) -> pd.Series:
    """Taxa encolhida para a taxa agregada do recorte (Beta-Binomial com prior fixo)."""
    referencia = eventos.sum() / casos.sum() if casos.sum() > 0 else 0.0
    return (eventos + pseudo_casos * referencia) / (casos + pseudo_casos)


def apply_criticality(features: pd.DataFrame) -> pd.DataFrame:
    """Calcula o score de criticidade e o nível (cortes fixos) por município."""
    f = features.copy()
    f["log_casos"] = np.log1p(f["casos"])

    # 1. Taxas suavizadas: poucos casos ficam perto da média do recorte.
    f["taxa_obito_suav"] = taxa_suavizada(f["obitos"], f["casos"], PSEUDO_CASOS_OBITO)
    f["taxa_hospitalizacao_suav"] = taxa_suavizada(
        f["hospitalizados"], f["casos"], PSEUDO_CASOS_HOSPITALIZACAO
    )

    # 2. Normalização min-max entre os municípios do recorte.
    f["norm_log_casos"] = _min_max(f["log_casos"])
    f["norm_taxa_obito"] = _min_max(f["taxa_obito_suav"])
    f["norm_taxa_hospitalizacao"] = _min_max(f["taxa_hospitalizacao_suav"])

    # 3. Severidade pesa proporcionalmente ao volume que a sustenta.
    f["credibilidade"] = f["casos"] / (f["casos"] + CASOS_CREDIBILIDADE)
    f["norm_taxa_obito"] *= f["credibilidade"]
    f["norm_taxa_hospitalizacao"] *= f["credibilidade"]

    # Score: volume (log) + severidade (óbitos e hospitalização).
    f["score_criticidade"] = (
        PESO_VOLUME * f["norm_log_casos"]
        + PESO_OBITO * f["norm_taxa_obito"]
        + PESO_HOSPITALIZACAO * f["norm_taxa_hospitalizacao"]
    ) * 100
    f["score_criticidade"] = f["score_criticidade"].round(1)

    # 4. Nível pelos cortes fixos; Crítico exige volume mínimo.
    f["nivel"] = f["score_criticidade"].apply(classificar)
    f["limitado_por_volume"] = (f["nivel"] == "Crítico") & (f["casos"] < MINIMO_CASOS_CRITICO)
    f.loc[f["limitado_por_volume"], "nivel"] = "Alto"
    return f.sort_values("score_criticidade", ascending=False).reset_index(drop=True)


def criticality_from_notifications(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Pipeline completo: features → corte no 1º quartil → score.

    Retorna o score por município e o valor do 1º quartil usado no corte.
    """
    if df.empty:
        raise ValueError("Não há notificações para calcular a criticidade.")
    base_features = build_features(df)
    q1 = float(base_features["casos"].quantile(0.25))
    base_features = base_features[base_features["casos"] > q1]
    return apply_criticality(base_features), q1
