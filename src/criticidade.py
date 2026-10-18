"""Score municipal de criticidade compartilhado pelos serviços analíticos."""

from __future__ import annotations

import numpy as np
import pandas as pd

PISO_CASOS = 50
PESO_VOLUME = 0.5
PESO_OBITO = 0.3
PESO_HOSPITALIZACAO = 0.2
CORTES = (("Crítico", 50), ("Alto", 35), ("Médio", 20), ("Baixo", float("-inf")))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por município para o clustering de criticidade."""
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


def apply_criticality(features: pd.DataFrame) -> pd.DataFrame:
    """Calcula o score de criticidade e o nível (cortes fixos) por município."""
    f = features.copy()
    f["log_casos"] = np.log1p(f["casos"])

    # Municípios abaixo do piso pontuam por volume: taxas zeradas (evita taxas infladas).
    sub_piso = f["casos"] < PISO_CASOS
    f.loc[sub_piso, "taxa_hospitalizacao"] = 0.0
    f.loc[sub_piso, "taxa_obito"] = 0.0

    # Normalização min-max para o score.
    f["norm_log_casos"] = (f["log_casos"] - f["log_casos"].min()) / (
        f["log_casos"].max() - f["log_casos"].min() + 1e-9
    )
    f["norm_taxa_obito"] = (f["taxa_obito"] - f["taxa_obito"].min()) / (
        f["taxa_obito"].max() - f["taxa_obito"].min() + 1e-9
    )
    f["norm_taxa_hospitalizacao"] = (
        f["taxa_hospitalizacao"] - f["taxa_hospitalizacao"].min()
    ) / (f["taxa_hospitalizacao"].max() - f["taxa_hospitalizacao"].min() + 1e-9)

    # Score: volume (log) + severidade (óbitos e hospitalização).
    f["score_criticidade"] = (
        PESO_VOLUME * f["norm_log_casos"]
        + PESO_OBITO * f["norm_taxa_obito"]
        + PESO_HOSPITALIZACAO * f["norm_taxa_hospitalizacao"]
    ) * 100
    f["score_criticidade"] = f["score_criticidade"].round(1)

    # Nível derivado do score, com cortes fixos (validado no Oracle).
    f["nivel"] = f["score_criticidade"].apply(classificar)
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
