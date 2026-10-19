from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api import analytics as a  # noqa: E402
from api.assist import executar_ferramenta, responder  # noqa: E402
from api.dataset import carregar, semana_epidemiologica  # noqa: E402
from api.main import app, dataset  # noqa: E402
from criticidade import apply_criticality, classificar  # noqa: E402

CABECALHO = "DT_NOTIFIC,NU_ANO,SG_UF_NOT,ID_MUNICIP,HOSPITALIZ,CLASSI_FIN,EVOLUCAO\n"
MUNICIPIOS = (
    "codigo_ibge,nome,latitude,longitude,capital,codigo_uf,siafi_id,ddd,fuso_horario\n"
    "3550308,São Paulo,-23.5,-46.6,1,35,1,11,America/Sao_Paulo\n"
    "1100205,Porto Velho,-8.7,-63.9,1,11,2,69,America/Porto_Velho\n"
    "5300108,Brasília,-15.8,-47.9,1,53,3,61,America/Sao_Paulo\n"
)


def _linhas(data: str, ano: str, mun: str, n: int, hosp="2", classi="10", evol="1") -> str:
    return "".join(f"{data},{ano},xx,{mun},{hosp},{classi},{evol}\n" for _ in range(n))


def criar_base(pasta: Path) -> None:
    b23 = CABECALHO
    b25 = (
        CABECALHO
        + _linhas("2025-01-06", "2025", "355030", 40)
        + _linhas("2025-01-07", "2025", "110020", 10, hosp="1", classi="12", evol="2")
        + _linhas("2025-01-08", "2026", "355030", 99)  # NU_ANO fora do arquivo anual: descartada
        + _linhas("2025-02-03", "2025", "530010", 5, classi="", evol="")
    )
    b26 = (
        CABECALHO
        + _linhas("2026-01-05", "2026", "355030", 80)
        + _linhas("2026-01-06", "2026", "110020", 5, hosp="1", classi="11", evol="4")
        + _linhas("2026-01-07", "2026", "530010", 3, classi="8")
        + _linhas("2099-01-01", "2026", "355030", 7)  # data futura: descartada
    )
    (pasta / "DENGBR23.csv").write_text(b23, encoding="latin-1")
    (pasta / "DENGBR24.csv").write_text(CABECALHO, encoding="latin-1")
    (pasta / "DENGBR25.csv").write_text(b25, encoding="latin-1")
    (pasta / "DENGBR26.csv").write_text(b26, encoding="latin-1")
    (pasta / "municipios.csv").write_text(MUNICIPIOS, encoding="utf-8")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        criar_base(Path(cls.tmp.name))
        cls.ds = carregar(Path(cls.tmp.name), hoje=pd.Timestamp("2026-10-17"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class SemanaEpidemiologicaTests(unittest.TestCase):
    def test_semana_1_contem_4_de_janeiro_e_2025_tem_53_semanas(self):
        datas = pd.Series(pd.to_datetime(["2024-12-29", "2025-12-28", "2026-01-03", "2026-01-04"]))
        ano, semana, inicio = semana_epidemiologica(datas)
        self.assertEqual(list(zip(ano, semana)), [(2025, 1), (2025, 53), (2025, 53), (2026, 1)])
        self.assertEqual(inicio.iloc[0], pd.Timestamp("2024-12-29"))


class CargaTests(Base):
    def test_usa_apenas_linhas_de_2023_da_fonte_completa(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            criar_base(directory)
            (directory / "DENGBR23.csv").write_text(
                CABECALHO
                + _linhas("2023-01-06", "2023", "355030", 10)
                + _linhas("2024-01-06", "2024", "355030", 2),
                encoding="latin-1",
            )
            (directory / "DENGBR24.csv").write_text(
                CABECALHO
                + _linhas("2024-02-06", "2024", "355030", 4)
                + _linhas("2023-12-31", "2023", "355030", 1),
                encoding="latin-1",
            )
            dataset = carregar(directory, hoje=pd.Timestamp("2026-10-17"))
        rows_2023 = dataset.notificacoes[
            dataset.notificacoes["data"].dt.year == 2023
        ]
        rows_2024 = dataset.notificacoes[
            dataset.notificacoes["data"].dt.year == 2024
        ]
        self.assertEqual(len(rows_2023), 10)
        self.assertEqual(len(rows_2024), 4)
        self.assertEqual(
            dataset.linhas_descartadas[
                "DENGBR23 com NU_ANO diferente de 2023"
            ],
            2,
        )
        self.assertEqual(
            dataset.linhas_descartadas[
                "DENGBR24 com NU_ANO diferente de 2024"
            ],
            1,
        )

    def test_aplica_regras_do_app_e_deriva_uf_do_municipio(self):
        df = self.ds.notificacoes
        self.assertEqual(len(df), 40 + 10 + 5 + 80 + 5 + 3)
        self.assertEqual(
            self.ds.linhas_descartadas["DENGBR23 com NU_ANO diferente de 2023"],
            0,
        )
        self.assertEqual(
            self.ds.linhas_descartadas["DENGBR25 com NU_ANO diferente de 2025"],
            99,
        )
        self.assertEqual(self.ds.linhas_descartadas["DT_NOTIFIC posterior à data de processamento"], 7)
        self.assertEqual(set(df.loc[df["id_municip"] == 110020, "uf"]), {"RO"})
        self.assertEqual(set(df.loc[df["id_municip"] == 530010, "uf"]), {"DF"})

    def test_confirmados_seguem_ficha_sinan(self):
        df = self.ds.notificacoes
        self.assertEqual(int(df["confirmado"].sum()), 40 + 10 + 80 + 5)
        self.assertEqual(int(df["grave"].sum()), 15)
        self.assertEqual(int(df["obito_dengue"].sum()), 10)
        self.assertEqual(int(df["obito_investigacao"].sum()), 5)


class AnaliticaTests(Base):
    def test_comparacao_anual_usa_mesmas_semanas(self):
        f = a.Filtros(inicio=date(2026, 1, 5), fim=date(2026, 1, 10))
        r = a.visao_geral(self.ds, f)
        self.assertEqual(r["comparacao"]["inicio"], date(2025, 1, 6))
        self.assertEqual(r["totais"]["notificacoes"], 88)
        self.assertEqual(r["comparacao"]["totais"]["notificacoes"], 50)
        self.assertEqual(r["comparacao"]["variacao_pct"]["notificacoes"], 76.0)

    def test_sem_comparacao_quando_periodo_anterior_nao_tem_cobertura(self):
        r = a.visao_geral(self.ds, a.Filtros())
        self.assertIsNone(r["comparacao"])
        self.assertIsNotNone(r["motivo_sem_comparacao"])

    def test_serie_marca_periodos_parciais(self):
        s = a.serie(self.ds, a.Filtros(inicio=date(2025, 1, 6), fim=date(2025, 1, 31)), "mes")
        self.assertEqual(len(s), 1)
        self.assertTrue(s[0]["parcial"])
        semanas = a.serie(self.ds, a.Filtros(inicio=date(2025, 1, 5), fim=date(2025, 1, 18)), "semana")
        self.assertEqual([p["periodo"] for p in semanas], ["SE 2/2025", "SE 3/2025"])
        self.assertEqual(semanas[1]["notificacoes"], 0)
        # A base de teste começa em 06/01, então a SE 2 (05/01–11/01) é parcial.
        self.assertEqual([p["parcial"] for p in semanas], [True, False])

    def test_ranking_pagina_e_ordena(self):
        r = a.ranking(self.ds, a.Filtros(), pagina=1, tamanho=1, ordenar="notificacoes", direcao="desc", busca=None, niveis=())
        self.assertEqual(r["total"], 3)
        self.assertEqual(r["itens"][0]["nome"], "São Paulo")
        busca = a.ranking(self.ds, a.Filtros(), pagina=1, tamanho=5, ordenar="nome", direcao="asc", busca="brasilia", niveis=())
        self.assertEqual([m["nome"] for m in busca["itens"]], ["Brasília"])

    def test_previsao_bloqueada_com_motivo_do_modelo(self):
        r = a.previsao(self.ds, a.Filtros())
        self.assertEqual(r["status"], "indisponivel")
        self.assertIn("24 meses", r["motivo"])
        self.assertEqual(r["previsao"], [])

    def test_previsao_reutiliza_modelo_para_mesmo_dataset_e_filtros(self):
        from modelos import series_temporais

        a.previsao.cache_clear()
        mensal = pd.Series(
            range(24),
            index=pd.date_range("2024-01-01", periods=24, freq="MS"),
        )
        tabela = pd.DataFrame(
            {
                "PREVISAO": [10],
                "LIMITE_INFERIOR_95": [5.0],
                "LIMITE_SUPERIOR_95": [15.0],
            },
            index=pd.date_range("2026-01-01", periods=1, freq="MS"),
        )
        validacao = {
            "model_mae": 1.0,
            "seasonal_naive_mae": 2.0,
            "model_rmse": 1.0,
            "seasonal_naive_rmse": 2.0,
            "beats_seasonal_naive": True,
            "test_observations": 9,
        }
        try:
            with (
                patch.object(
                    series_temporais,
                    "prepare_monthly_cases",
                    return_value=mensal,
                ),
                patch.object(
                    series_temporais,
                    "forecast_monthly_cases",
                    return_value=tabela,
                ) as forecast,
                patch.object(
                    series_temporais,
                    "rolling_backtest",
                    return_value=validacao,
                ),
            ):
                first = a.previsao(self.ds, a.Filtros())
                second = a.previsao(self.ds, a.Filtros())
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "disponivel")
            self.assertEqual(forecast.call_count, 1)
        finally:
            a.previsao.cache_clear()

    def test_pacientes_indisponivel_sem_colunas_clinicas(self):
        r = a.pacientes_status(self.ds)
        self.assertFalse(r["disponivel"])
        self.assertIn("FEBRE", r["colunas_faltando"])


class CriticidadeTests(unittest.TestCase):
    def test_cortes_fixos(self):
        self.assertEqual([classificar(v) for v in (50, 49.9, 35, 20, 19.9)], ["Crítico", "Alto", "Alto", "Médio", "Baixo"])

    def test_piso_zera_taxas_e_pesos_do_app(self):
        f = pd.DataFrame(
            {
                "id_municip": [1, 2, 3],
                "casos": [1000, 100, 10],
                "obitos": [10, 0, 5],
                "hospitalizados": [100, 0, 10],
                "UF": ["SP"] * 3,
            }
        )
        f["taxa_hospitalizacao"] = f["hospitalizados"] / f["casos"]
        f["taxa_obito"] = f["obitos"] / f["casos"]
        r = apply_criticality(f).set_index("id_municip")
        self.assertEqual(r.loc[3, "taxa_obito"], 0.0)  # abaixo do piso de 50 casos
        self.assertAlmostEqual(r.loc[1, "score_criticidade"], 100.0, places=1)
        self.assertEqual(r.loc[3, "score_criticidade"], 0.0)


class RotasTests(Base):
    def setUp(self):
        app.dependency_overrides[dataset] = lambda: self.ds
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_valida_filtros(self):
        self.assertEqual(self.client.get("/api/visao-geral?uf=XX").status_code, 400)
        self.assertEqual(self.client.get("/api/visao-geral?inicio=2026-02-01&fim=2026-01-01").status_code, 400)
        self.assertEqual(self.client.get("/api/municipios?nivel=Grave").status_code, 400)
        self.assertEqual(self.client.get("/api/municipios?ordenar=drop").status_code, 400)

    def test_rotas_principais_respondem(self):
        for rota in ("/api/meta", "/api/visao-geral", "/api/series", "/api/series/anual", "/api/distribuicoes",
                     "/api/municipios", "/api/mapa", "/api/previsao", "/api/pacientes/status", "/api/assist/status"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, 200)

    def test_detalhe_municipio_inexistente(self):
        self.assertEqual(self.client.get("/api/municipios/999999").status_code, 404)

    def test_export_csv(self):
        r = self.client.get("/api/export/agregado.csv?uf=SP")
        self.assertEqual(r.status_code, 200)
        linhas = r.content.decode("utf-8-sig").strip().splitlines()
        self.assertTrue(linhas[0].startswith("mes;uf;codigo_ibge"))
        self.assertTrue(all(";SP;" in linha for linha in linhas[1:]))

    def test_assist_sem_chave_retorna_503(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            r = self.client.post("/api/assist", json={"mensagens": [{"papel": "usuario", "texto": "oi"}]})
        self.assertEqual(r.status_code, 503)


class AssistTests(Base):
    def test_ferramenta_consulta_dados_reais(self):
        r = executar_ferramenta(self.ds, "visao_geral", {"ufs": ["RO"]})
        self.assertEqual(r["totais"]["notificacoes"], 15)

    def test_laco_executa_ferramenta_e_retorna_texto(self):
        chamadas = []

        def falso(**kwargs):
            chamadas.append(kwargs)
            if len(chamadas) == 1:
                bloco = SimpleNamespace(type="tool_use", id="t1", name="visao_geral", input={"ufs": ["SP"]})
                return SimpleNamespace(stop_reason="tool_use", content=[bloco])
            resultado = chamadas[1]["messages"][-1]["content"][0]
            self.assertEqual(resultado["type"], "tool_result")
            self.assertIn('"notificacoes": 120', resultado["content"])
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="120 notificações.")])

        r = responder(self.ds, [{"papel": "usuario", "texto": "Quantas notificações em SP?"}], falso, "modelo")
        self.assertEqual(r["texto"], "120 notificações.")
        self.assertEqual(r["consultas"], [{"ferramenta": "visao_geral", "parametros": {"ufs": ["SP"]}}])


if __name__ == "__main__":
    unittest.main()
