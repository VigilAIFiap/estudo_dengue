from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api import analytics as a  # noqa: E402
from api.dataset import carregar, semana_epidemiologica  # noqa: E402
from api.main import DATA_SOURCE, app, dataset  # noqa: E402
from api.triage_intake import AssessmentResult  # noqa: E402
from criticidade import classificar  # noqa: E402

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


_AMBIENTE = None


def setUpModule():
    # Os dados sintéticos não têm ID_MN_RESI: todo o arquivo ignora o DENGUE_MUNICIPIO_BASE do .env local.
    global _AMBIENTE
    _AMBIENTE = patch.dict("os.environ")
    _AMBIENTE.start()
    os.environ.pop("DENGUE_MUNICIPIO_BASE", None)


def tearDownModule():
    _AMBIENTE.stop()


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

class CriticidadeTests(unittest.TestCase):
    def test_cortes_fixos(self):
        self.assertEqual([classificar(v) for v in (50, 49.9, 35, 20, 19.9)], ["Crítico", "Alto", "Alto", "Médio", "Baixo"])


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
                     "/api/municipios", "/api/mapa", "/api/previsao"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, 200)
        self.assertEqual(self.client.get("/api/assist/status").status_code, 404)

    def test_meta_informa_a_fonte_configurada(self):
        resposta = self.client.get("/api/meta")
        self.assertEqual(resposta.json()["fonte_dados"], DATA_SOURCE)

    def test_series_reutiliza_resultado_em_consultas_repetidas(self):
        a.serie.cache_clear()
        filtros = a.Filtros()
        primeiro = a.serie(self.ds, filtros, "mes")
        segundo = a.serie(self.ds, filtros, "mes")
        self.assertIs(primeiro, segundo)
        self.assertEqual(a.serie.cache_info().hits, 1)

    def test_detalhe_municipio_inexistente(self):
        self.assertEqual(self.client.get("/api/municipios/999999").status_code, 404)

    def test_export_csv(self):
        r = self.client.get("/api/export/agregado.csv?uf=SP")
        self.assertEqual(r.status_code, 200)
        linhas = r.content.decode("utf-8-sig").strip().splitlines()
        self.assertTrue(linhas[0].startswith("mes;uf;codigo_ibge"))
        self.assertTrue(all(";SP;" in linha for linha in linhas[1:]))

    def test_healthz_responde_para_a_hospedagem(self):
        resposta = self.client.get("/healthz")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok"})

    def test_mapa_informa_municipios_sem_notificacao_e_sem_score(self):
        r = self.client.get("/api/mapa").json()
        self.assertEqual(len(r["pontos"]) + r["sem_notificacao"], r["cadastro"])
        self.assertGreaterEqual(r["sem_notificacao"], 0)
        self.assertLessEqual(r["sem_score"], len(r["pontos"]))

    def test_triage_form_requires_explicit_enablement(self):
        with patch.dict("os.environ", {"TRIAGE_FORM_ENABLED": "false"}):
            response = self.client.post(
                "/api/pacientes/avaliacao",
                json={"age_group": "20-39"},
                headers={"Origin": "http://localhost:3000"},
            )
        self.assertEqual(response.status_code, 503)

    def test_triage_form_stores_only_allowlisted_fields(self):
        with patch.dict("os.environ", {"TRIAGE_FORM_ENABLED": "true"}), patch(
            "api.main.save_assessment",
            return_value=AssessmentResult(
                intake_id=42,
                status="PENDENTE",
                missing_fields=("FEBRE",),
                inconsistencies=(),
            ),
        ) as save:
            response = self.client.post(
                "/api/pacientes/avaliacao",
                json={"age_group": "20-39", "fever": "SIM"},
                headers={"Origin": "http://localhost:3000"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "intake_id": 42,
                "status": "PENDENTE",
                "campos_faltantes": ["FEBRE"],
                "inconsistencias": [],
            },
        )
        self.assertEqual(save.call_args.args[0].age_group, "20-39")
        self.assertEqual(save.call_args.args[0].fever, "SIM")
        self.assertIsNone(save.call_args.args[0].sex)

    def test_triage_form_reports_automatic_approval(self):
        with patch.dict("os.environ", {"TRIAGE_FORM_ENABLED": "true"}), patch(
            "api.main.save_assessment",
            return_value=AssessmentResult(intake_id=7, status="APROVADO"),
        ):
            response = self.client.post(
                "/api/pacientes/avaliacao",
                json={"age_group": "20-39"},
                headers={"Origin": "http://localhost:3000"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "intake_id": 7,
                "status": "APROVADO",
                "campos_faltantes": [],
                "inconsistencias": [],
            },
        )

    def test_triage_form_rejects_unapproved_fields_and_origins(self):
        with patch.dict("os.environ", {"TRIAGE_FORM_ENABLED": "true"}):
            bad_origin = self.client.post(
                "/api/pacientes/avaliacao",
                json={},
                headers={"Origin": "https://untrusted.example"},
            )
            extra_field = self.client.post(
                "/api/pacientes/avaliacao",
                json={"patient_name": "Sensitive"},
                headers={"Origin": "http://localhost:3000"},
            )

        self.assertEqual(bad_origin.status_code, 403)
        self.assertEqual(extra_field.status_code, 422)


if __name__ == "__main__":
    unittest.main()
