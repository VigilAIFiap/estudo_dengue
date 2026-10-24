from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from criticidade import (  # noqa: E402
    PESO_HOSPITALIZACAO,
    PESO_OBITO,
    SUAVIZACAO_CASOS,
    apply_criticality,
    build_features,
    classificar,
    criticality_from_notifications,
)


def _municipios(linhas: list[tuple[int, int, int, int]]) -> pd.DataFrame:
    """(id, casos, obitos, hospitalizados) -> tabela de features como a de build_features."""
    f = pd.DataFrame(linhas, columns=["id_municip", "casos", "obitos", "hospitalizados"])
    f["UF"] = "SP"
    f["taxa_obito"] = f["obitos"] / f["casos"]
    f["taxa_hospitalizacao"] = f["hospitalizados"] / f["casos"]
    return f


class ScoreDeCriticidadeTests(unittest.TestCase):
    def test_pesos_da_severidade_somam_um(self):
        self.assertAlmostEqual(PESO_OBITO + PESO_HOSPITALIZACAO, 1.0)

    def test_cortes_fixos(self):
        self.assertEqual(
            [classificar(v) for v in (50, 49.9, 35, 20, 19.9)],
            ["Crítico", "Alto", "Alto", "Médio", "Baixo"],
        )

    def test_score_e_o_produto_do_fator_de_volume_pela_severidade(self):
        f = _municipios([(1, 10000, 10, 500), (2, 1000, 2, 40), (3, 100, 0, 5), (4, 60, 1, 6)])
        r = apply_criticality(f)
        esperado = (r["norm_log_casos"] * r["severidade"] * 100).round(1)
        pd.testing.assert_series_equal(r["score_criticidade"], esperado, check_names=False)
        self.assertTrue(r["score_criticidade"].between(0, 100).all())

    def test_casos_multiplicam_a_severidade(self):
        # Mesma taxa de óbito e de hospitalização: quem tem mais casos pontua mais.
        f = _municipios([(1, 5000, 50, 500), (2, 500, 5, 50), (3, 100, 1, 10), (4, 20, 0, 0)])
        r = apply_criticality(f).set_index("id_municip")
        self.assertGreater(r.loc[1, "score_criticidade"], r.loc[2, "score_criticidade"])
        self.assertGreater(r.loc[2, "score_criticidade"], r.loc[3, "score_criticidade"])
        self.assertEqual(r.loc[4, "score_criticidade"], 0.0)  # menor volume do recorte

    def test_com_o_mesmo_volume_a_severidade_decide(self):
        f = _municipios([(1, 1000, 0, 0), (2, 1000, 20, 300), (3, 100, 1, 10)])
        r = apply_criticality(f).set_index("id_municip")
        self.assertEqual(r.loc[1, "norm_log_casos"], r.loc[2, "norm_log_casos"])
        self.assertGreater(r.loc[2, "score_criticidade"], r.loc[1, "score_criticidade"])

    def test_poucos_casos_nao_viram_critico_por_taxa_alta(self):
        # 4 óbitos em 62 casos (6,5%) não pode superar cidades grandes com taxa comum.
        f = _municipios([(1, 80000, 80, 3800), (2, 60000, 100, 3500), (3, 62, 4, 10), (4, 300, 0, 10)])
        r = apply_criticality(f).set_index("id_municip")
        self.assertLess(r.loc[3, "score_criticidade"], r.loc[1, "score_criticidade"])
        self.assertLess(r.loc[3, "score_criticidade"], r.loc[2, "score_criticidade"])

    def test_taxas_sao_suavizadas_em_direcao_a_media_do_recorte(self):
        f = _municipios([(1, 10000, 10, 100), (2, 5, 1, 1)])  # 20% de óbito bruto com 5 casos
        r = apply_criticality(f).set_index("id_municip")
        taxa_geral = f["obitos"].sum() / f["casos"].sum()
        suavizada = r.loc[2, "taxa_obito_suavizada"]
        self.assertLess(suavizada, r.loc[2, "taxa_obito"])
        self.assertLess(abs(suavizada - taxa_geral), abs(r.loc[2, "taxa_obito"] - taxa_geral))
        self.assertAlmostEqual(
            suavizada, (1 + SUAVIZACAO_CASOS * taxa_geral) / (5 + SUAVIZACAO_CASOS), places=9
        )

    def test_um_municipio_atipico_nao_comprime_os_demais(self):
        # Com min-max, a taxa extrema zerava a severidade dos outros; com percentil não.
        linhas = [(i, 1000 + i, i % 5, 20 + i % 7) for i in range(1, 31)]
        linhas.append((99, 200, 30, 150))  # taxa de óbito atípica
        r = apply_criticality(_municipios(linhas))
        outros = r[r["id_municip"] != 99]
        self.assertGreater(outros["pct_taxa_obito"].median(), 0.2)

    def test_pipeline_descarta_municipios_ate_o_primeiro_quartil(self):
        ids = np.repeat([1, 2, 3, 4], [100, 40, 8, 2])
        df = pd.DataFrame({"ID_MUNICIP": ids, "obito": 0, "hospitalizado": 0, "UF": "SP"})
        df.loc[df.index[:3], "obito"] = 1
        r, q1 = criticality_from_notifications(df)
        self.assertEqual(q1, 6.5)  # 1º quartil de [2, 8, 40, 100]
        self.assertEqual(set(r["id_municip"]), {1, 2, 3})  # só o município com 2 casos fica de fora
        self.assertEqual(q1, float(build_features(df)["casos"].quantile(0.25)))

    def test_recorte_com_um_so_municipio_nao_quebra(self):
        r = apply_criticality(_municipios([(1, 100, 1, 10)]))
        self.assertEqual(len(r), 1)
        self.assertEqual(r.loc[0, "score_criticidade"], 0.0)


if __name__ == "__main__":
    unittest.main()
