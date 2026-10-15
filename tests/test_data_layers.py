from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import gerar_gold
import oracle_upload


class FakeCursor:
    def __init__(self, fail_insert=False):
        self.statements = []
        self.fail_insert = fail_insert
        self.current_table = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, **binds):
        self.statements.append((statement, binds))
        if 'USER_TAB_COLUMNS' in statement:
            self.current_table = binds['table_name']

    def fetchall(self):
        return [('VALUE', 'Y', None)]

    def executemany(self, statement, rows):
        if self.fail_insert:
            raise RuntimeError('simulated insert failure')
        self.statements.append((statement, rows))


class FakeConnection:
    def __init__(self, fail_insert=False):
        self.cursor_instance = FakeCursor(fail_insert=fail_insert)
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


class DataLayerTests(unittest.TestCase):
    def test_oracle_value_normalization(self):
        timestamp = pd.Timestamp('2025-01-02 03:04:05')
        self.assertIsNone(oracle_upload._normalize_value(np.nan))
        self.assertEqual(oracle_upload._normalize_value(True), 1)
        self.assertEqual(
            oracle_upload._normalize_value(timestamp),
            timestamp.to_pydatetime(),
        )

    def test_invalid_oracle_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            oracle_upload._validate_table_name('PRATA; DROP TABLE USERS')

    def test_replace_commits_both_layers_together(self):
        connection = FakeConnection()
        frame = pd.DataFrame({'VALUE': [1, 2]})
        with patch.object(
            oracle_upload, 'con_sql', return_value=(connection, 'connected')
        ):
            oracle_upload.replace_tables(
                {
                    'prata': ('PRATA', frame),
                    'ouro': ('OURO', frame),
                },
                batch_size=1,
            )
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)
        self.assertEqual(
            connection.cursor_instance.statements[0][0],
            'ALTER SESSION DISABLE PARALLEL DML',
        )
        self.assertEqual(
            sum(
                'DELETE FROM ' in sql
                for sql, _ in connection.cursor_instance.statements
            ),
            2,
        )

    def test_replace_rolls_back_insert_failure(self):
        connection = FakeConnection(fail_insert=True)
        frame = pd.DataFrame({'VALUE': [1]})
        with patch.object(
            oracle_upload, 'con_sql', return_value=(connection, 'connected')
        ):
            with self.assertRaisesRegex(RuntimeError, 'simulated insert failure'):
                oracle_upload.replace_tables(
                    {'prata': ('PRATA', frame)}, batch_size=1
                )
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_gold_aggregates_month_and_fills_municipality(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            municipality_path = directory / 'municipios.csv'
            municipality_path.write_text(
                'codigo_ibge,nome,codigo_uf\n3550308,Sao Paulo,35\n',
                encoding='utf-8',
            )
            input_path = directory / 'prata.parquet'
            output_path = directory / 'ouro.parquet'
            pd.DataFrame(
                {
                    'DT_NOTIFIC': pd.to_datetime(
                        ['2025-01-03', '2025-01-12']
                    ),
                    'ID_MUNICIP': pd.Series([355030, 355030], dtype='Int64'),
                    'UF': ['35', '35'],
                    'MUNICIPIO': ['355030', 'Sao Paulo'],
                    'CLASSI_FIN': ['dengue', 'descartado'],
                    'EVOLUCAO': [None, 'obito_dengue'],
                    'HOSPITALIZ': ['1', '2'],
                }
            ).to_parquet(input_path, index=False)

            with patch.object(gerar_gold, 'DADOS', directory):
                result = gerar_gold.gold_acumulado_municipio(
                    input_path=input_path,
                    output_path=output_path,
                )

            self.assertEqual(len(result), 1)
            self.assertFalse(
                result.duplicated(['MES_REFERENCIA', 'ID_MUNICIP']).any()
            )
            row = result.iloc[0]
            self.assertEqual(row['MUNICIPIO'], 'Sao Paulo')
            self.assertEqual(row['UF'], '35')
            self.assertEqual(int(row['NOTIFICACOES']), 2)
            self.assertEqual(int(row['CASOS_DENGUE']), 1)
            self.assertEqual(int(row['OBITOS_DENGUE']), 1)
            self.assertEqual(int(row['HOSPITALIZACOES']), 1)


if __name__ == '__main__':
    unittest.main()
