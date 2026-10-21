from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from api import oracle_dataset


class FakeCursor:
    def __init__(self, batches):
        self.batches = list(batches)
        self.query = None
        self.arraysize = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query):
        self.query = query

    def fetchmany(self, _size):
        return self.batches.pop(0) if self.batches else []


class FakeConnection:
    def __init__(self, batches):
        self.cursor_instance = FakeCursor(batches)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class OracleDatasetTests(unittest.TestCase):
    def test_loads_prata_codes_into_api_dataset_and_closes_connection(self):
        connection = FakeConnection(
            [
                [
                    (pd.Timestamp("2023-12-31"), 355030, 2, "dengue", "cura"),
                    (pd.Timestamp("2025-01-01"), 355030, 1, "dengue", "obito_dengue"),
                    (pd.Timestamp("2025-01-02"), 355030, 2, "dengue_grave", "cura"),
                ],
                [
                    (pd.Timestamp("2099-01-01"), 355030, 1, "dengue", "cura"),
                    (None, 355030, 2, "descartado", "ignorado"),
                ],
            ]
        )
        with TemporaryDirectory() as temporary_directory:
            municipalities = Path(temporary_directory) / "municipios.csv"
            municipalities.write_text(
                "codigo_ibge,nome,latitude,longitude,capital,codigo_uf\n"
                "3550308,Sao Paulo,-23.5,-46.6,1,35\n",
                encoding="utf-8",
            )
            with patch.object(
                oracle_dataset, "con_sql",
                return_value=(connection, "connected"),
            ):
                dataset = oracle_dataset.carregar_oracle(
                    municipalities,
                    table_name="PRATA",
                    hoje=pd.Timestamp("2025-12-31"),
                )

        self.assertTrue(connection.closed)
        self.assertEqual(
            connection.cursor_instance.query,
            "SELECT DT_NOTIFIC, ID_MUNICIP, HOSPITALIZ, CLASSI_FIN, EVOLUCAO "
            "FROM PRATA",
        )
        self.assertEqual(len(dataset.notificacoes), 3)
        self.assertEqual(int(dataset.notificacoes["confirmado"].sum()), 3)
        self.assertEqual(int(dataset.notificacoes["grave"].sum()), 1)
        self.assertEqual(int(dataset.notificacoes["obito_dengue"].sum()), 1)
        self.assertEqual(dataset.linhas_descartadas["DT_NOTIFIC inválida"], 1)
        self.assertEqual(
            dataset.linhas_descartadas[
                "DT_NOTIFIC posterior à data de processamento"
            ],
            1,
        )
        self.assertEqual(set(dataset.notificacoes["uf"].astype(str)), {"SP"})
        self.assertEqual(
            set(dataset.notificacoes["data"].dt.year),
            {2023, 2025},
        )

    def test_rejects_invalid_table_name_before_connecting(self):
        with patch.object(oracle_dataset, "con_sql") as connect:
            with self.assertRaisesRegex(ValueError, "Nome de tabela Oracle inválido"):
                oracle_dataset.carregar_oracle(
                    Path("municipios.csv"),
                    table_name="PRATA; DROP TABLE USERS",
                )
        connect.assert_not_called()

    def test_closes_connection_when_query_fails(self):
        class FailedCursor(FakeCursor):
            def execute(self, _query):
                raise RuntimeError("query failed")

        connection = FakeConnection([])
        connection.cursor_instance = FailedCursor([])
        with TemporaryDirectory() as temporary_directory:
            municipalities = Path(temporary_directory) / "municipios.csv"
            municipalities.write_text(
                "codigo_ibge,nome,latitude,longitude,capital,codigo_uf\n"
                "3550308,Sao Paulo,-23.5,-46.6,1,35\n",
                encoding="utf-8",
            )
            with patch.object(
                oracle_dataset, "con_sql",
                return_value=(connection, "connected"),
            ):
                with self.assertRaisesRegex(RuntimeError, "query failed"):
                    oracle_dataset.carregar_oracle(municipalities)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
