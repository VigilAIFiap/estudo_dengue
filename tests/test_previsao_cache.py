from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from api import analytics as a  # noqa: E402
from api.dataset import carregar  # noqa: E402
from modelos import series_temporais  # noqa: E402
from test_municipio_base import criar_base  # noqa: E402


class PrevisaoEmCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ambiente = patch.dict("os.environ")
        cls.ambiente.start()
        os.environ.pop("DENGUE_MUNICIPIO_BASE", None)
        cls.tmp = TemporaryDirectory()
        criar_base(Path(cls.tmp.name))
        cls.ds = carregar(Path(cls.tmp.name), hoje=pd.Timestamp("2026-10-17"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.ambiente.stop()

    def setUp(self):
        a.previsao.cache_clear()
        self.chamadas = 0
        self.trava = threading.Lock()
        mensal = pd.Series(range(24), index=pd.date_range("2024-01-01", periods=24, freq="MS"))
        tabela = pd.DataFrame(
            {"PREVISAO": [10], "LIMITE_INFERIOR_95": [5.0], "LIMITE_SUPERIOR_95": [15.0]},
            index=pd.date_range("2026-01-01", periods=1, freq="MS"),
        )
        validacao = {
            "model_mae": 1.0, "seasonal_naive_mae": 2.0, "model_rmse": 1.0, "seasonal_naive_rmse": 2.0,
            "beats_seasonal_naive": True, "test_observations": 9,
        }

        def prever(_serie, months=12):
            with self.trava:
                self.chamadas += 1
            time.sleep(0.3)  # simula o ajuste lento do SARIMA
            return tabela

        for alvo, substituto in (
            ("prepare_monthly_cases", lambda *_a, **_k: mensal),
            ("forecast_monthly_cases", prever),
            ("rolling_backtest", lambda *_a, **_k: validacao),
        ):
            parte = patch.object(series_temporais, alvo, substituto)
            parte.start()
            self.addCleanup(parte.stop)

    def test_periodo_nao_gera_novo_ajuste(self):
        primeira = a.previsao(self.ds, a.Filtros())
        segunda = a.previsao(self.ds, a.Filtros(inicio=date(2025, 1, 1), fim=date(2025, 6, 30)))
        self.assertEqual(self.chamadas, 1)
        self.assertIs(primeira, segunda)
        self.assertEqual(primeira["status"], "disponivel")

    def test_recorte_geografico_diferente_gera_novo_ajuste(self):
        a.previsao(self.ds, a.Filtros())
        a.previsao(self.ds, a.Filtros(ufs=("SP",)))
        self.assertEqual(self.chamadas, 2)

    def test_pedidos_simultaneos_calculam_uma_so_vez(self):
        resultados = []

        def pedir():
            resultados.append(a.previsao(self.ds, a.Filtros(inicio=date(2025, 3, 1))))

        fios = [threading.Thread(target=pedir) for _ in range(5)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=30)
        self.assertEqual(self.chamadas, 1)
        self.assertEqual(len(resultados), 5)
        self.assertTrue(all(r is resultados[0] for r in resultados))

    def test_cache_clear_forca_novo_calculo(self):
        a.previsao(self.ds, a.Filtros())
        a.previsao.cache_clear()
        a.previsao(self.ds, a.Filtros())
        self.assertEqual(self.chamadas, 2)

    def test_limpar_caches_geral_tambem_limpa_a_previsao(self):
        a.previsao(self.ds, a.Filtros())
        a.limpar_caches()
        a.previsao(self.ds, a.Filtros())
        self.assertEqual(self.chamadas, 2)


if __name__ == "__main__":
    unittest.main()
