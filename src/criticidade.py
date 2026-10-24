"""Score municipal de criticidade compartilhado pelos serviços analíticos.

Fórmula (a partir da revisão de calibração):

    score = 100 × fator_de_volume × severidade

* fator_de_volume: log das notificações normalizado entre 0 e 1 no recorte. O número de casos
  funciona como multiplicador: quem tem poucos casos não chega a níveis altos só por ter taxas altas.
* severidade: 60% percentil da taxa de óbito + 40% percentil da taxa de hospitalização. Os percentis
  (em vez de min-max) impedem que um único município atípico comprima todos os outros.
* as taxas de cada município são suavizadas em direção à taxa geral do recorte, com peso de
  SUAVIZACAO_CASOS casos, para que poucos casos não produzam taxas infladas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUAVIZACAO_CASOS = 50
PESO_OBITO = 0.6
PESO_HOSPITALIZACAO = 0.4
CORTES = (("Crítico", 50), ("Alto", 35), ("Médio", 20), ("Baixo", float("-inf")))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por município para o cálculo de criticidade."""
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


def _percentil(serie: pd.Series) -> pd.Series:
    """Posto percentual (0 a 1) entre os municípios do recorte; empates recebem o posto médio."""
    if serie.empty:
        return serie.astype(float)
    return (serie.rank(method="average") - 0.5) / len(serie)


def _suavizar(eventos: pd.Series, casos: pd.Series) -> pd.Series:
    """Taxa de eventos por caso, puxada para a taxa geral com peso de SUAVIZACAO_CASOS casos."""
    total_casos = float(casos.sum())
    taxa_geral = float(eventos.sum()) / total_casos if total_casos else 0.0
    return (eventos + SUAVIZACAO_CASOS * taxa_geral) / (casos + SUAVIZACAO_CASOS)


def apply_criticality(features: pd.DataFrame) -> pd.DataFrame:
    """Calcula o score de criticidade e o nível (cortes fixos) por município."""
    f = features.copy()
    f["log_casos"] = np.log1p(f["casos"])

    f["taxa_obito_suavizada"] = _suavizar(f["obitos"], f["casos"])
    f["taxa_hospitalizacao_suavizada"] = _suavizar(f["hospitalizados"], f["casos"])

    # Fator de volume: log das notificações, normalizado de 0 a 1 entre os municípios do recorte.
    amplitude = f["log_casos"].max() - f["log_casos"].min()
    f["norm_log_casos"] = (f["log_casos"] - f["log_casos"].min()) / (amplitude + 1e-9)

    # Severidade: percentis das taxas suavizadas (robustos a municípios atípicos).
    f["pct_taxa_obito"] = _percentil(f["taxa_obito_suavizada"])
    f["pct_taxa_hospitalizacao"] = _percentil(f["taxa_hospitalizacao_suavizada"])
    f["severidade"] = PESO_OBITO * f["pct_taxa_obito"] + PESO_HOSPITALIZACAO * f["pct_taxa_hospitalizacao"]

    # O número de casos (via fator de volume) multiplica a severidade.
    f["score_criticidade"] = (f["norm_log_casos"] * f["severidade"] * 100).round(1)

    # Nível derivado do score, com cortes fixos.
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
