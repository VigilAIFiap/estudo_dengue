from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import oracle_quality_upload as quality_upload


CSV_HEADER = "DT_NOTIFIC,ID_MUNICIP,IDADE_ANOS,FEBRE\n"


class FakeVar:
    def __init__(self, _type):
        self.value = None

    def setvalue(self, _position, value):
        self.value = value

    def getvalue(self):
        return self.value[0]


class FakeCursor:
    def __init__(self):
        self.rows = []
        self.findings = []
        self.result = []
        self.next_record_id = 100
        self.batch_var = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def var(self, value_type):
        return FakeVar(value_type)

    def execute(self, statement, binds=None):
        binds = binds or {}
        if "SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')" in statement:
            self.result = [("VIGIL_APEX",)]
        elif "SELECT RULE_CODE, SEVERITY" in statement:
            self.result = [
                (rule_code, "ALERTA")
                for rule_code in quality_upload.RULE_CODES
            ]
        elif "INSERT INTO VIGIL_DQ_BATCH" in statement:
            self.batch_var = binds["batch_id"]
            self.batch_var.setvalue(0, [7])
        elif "SELECT REGISTRO_ID, SOURCE_ROW" in statement:
            batch_id = binds["batch_id"]
            first = binds["first_row"]
            last = binds["last_row"]
            self.result = [
                (self.next_record_id + source_row, source_row)
                for row_batch_id, source_row, *_ in self.rows
                if row_batch_id == batch_id and first <= source_row <= last
            ]
        else:
            self.result = []

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None

    def executemany(self, statement, rows):
        if "INSERT INTO VIGIL_DQ_RECORD" in statement:
            self.rows.extend(rows)
        elif "INSERT INTO VIGIL_DQ_FINDING" in statement:
            self.findings.extend(rows)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class OracleQualityUploadTests(unittest.TestCase):
    def _inputs(self, directory: Path) -> tuple[Path, Path]:
        csv_path = directory / "entrada.csv"
        csv_path.write_text(
            CSV_HEADER
            + "2025-01-02,355030,35,1\n"
            + "2099-01-02,999999,150,2\n",
            encoding="utf-8",
        )
        municipalities_path = directory / "municipios.csv"
        municipalities_path.write_text(
            "codigo_ibge,nome\n3550308,Sao Paulo\n",
            encoding="utf-8",
        )
        return csv_path, municipalities_path

    def test_preview_counts_rules_without_database_write(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path, municipalities_path = self._inputs(Path(temporary_directory))
            result = quality_upload.preview_csv(
                csv_path,
                municipalities_path,
                reference_date=date(2025, 12, 31),
                batch_size=1,
            )

        self.assertEqual(result, {
            "linhas": 2,
            "DT_NOTIFIC_FUTURA": 1,
            "IDADE_FORA_INTERVALO": 1,
            "MUNICIPIO_NAO_RECONHECIDO": 1,
        })

    def test_rejects_unapproved_columns_before_oracle_connection(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            csv_path, municipalities_path = self._inputs(directory)
            csv_path.write_text(
                "DT_NOTIFIC,ID_MUNICIP,CPF\n2025-01-01,355030,123\n",
                encoding="utf-8",
            )
            with patch.object(quality_upload, "con_sql") as connect:
                with self.assertRaisesRegex(
                    quality_upload.CsvInputError,
                    "colunas fora do escopo permitido",
                ):
                    quality_upload.preview_csv(csv_path, municipalities_path)
            connect.assert_not_called()

    def test_import_persists_rows_and_validation_findings_atomically(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path, municipalities_path = self._inputs(Path(temporary_directory))
            connection = FakeConnection()
            with patch.object(
                quality_upload,
                "con_sql",
                return_value=(connection, "connected"),
            ):
                batch_id, result = quality_upload.import_csv(
                    csv_path,
                    municipalities_path,
                    reference_date=date(2025, 12, 31),
                    batch_size=1,
                    created_by="analyst",
                )

        self.assertEqual(batch_id, 7)
        self.assertEqual(result["linhas"], 2)
        self.assertEqual(result["DT_NOTIFIC_FUTURA"], 1)
        self.assertEqual(result["IDADE_FORA_INTERVALO"], 1)
        self.assertEqual(result["MUNICIPIO_NAO_RECONHECIDO"], 1)
        self.assertEqual(len(connection.cursor_instance.rows), 2)
        self.assertEqual(len(connection.cursor_instance.findings), 3)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_import_refuses_unexpected_oracle_schema(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path, municipalities_path = self._inputs(Path(temporary_directory))
            connection = FakeConnection()
            with patch.object(
                quality_upload,
                "con_sql",
                return_value=(connection, "connected"),
            ), patch.dict("os.environ", {"VIGIL_DQ_SCHEMA": "OTHER_SCHEMA"}):
                with self.assertRaisesRegex(RuntimeError, "Schema Oracle ativo"):
                    quality_upload.import_csv(csv_path, municipalities_path)

        self.assertTrue(connection.rolled_back)
        self.assertEqual(connection.cursor_instance.rows, [])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
