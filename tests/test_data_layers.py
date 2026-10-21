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
        if 'user_tab_columns' in statement:
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

    def test_streaming_staging_loader_checks_parquet_aggregates(self):
        gold = pd.DataFrame(
            {
                'MES_REFERENCIA': pd.to_datetime(
                    ['2025-01-01', '2025-01-01', '2025-02-01']
                ),
                'ID_MUNICIP': [355030, 110020, 355030],
                'UF': ['35', '11', '35'],
                'MUNICIPIO': ['Sao Paulo', 'Porto Velho', 'Sao Paulo'],
                'NOTIFICACOES': [10, 5, 3],
                'CASOS_DENGUE': [8, 3, 2],
                'OBITOS_DENGUE': [1, 0, 0],
                'HOSPITALIZACOES': [2, 1, 1],
            }
        )

        class Cursor:
            def __init__(self):
                self.rows = []
                self.statements = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, statement, **binds):
                self.statements.append(statement)
                if 'user_tab_columns' in statement:
                    self.rows = [
                        (str(column).upper(), 'Y', None)
                        for column in gold.columns
                    ]
                elif statement.startswith('SELECT COUNT(*) FROM OURO_STG'):
                    self.rows = [(len(gold),)]
                elif 'GROUP BY TRUNC(MES_REFERENCIA' in statement:
                    quality = oracle_upload._expected_monthly_quality('ouro', gold)
                    self.rows = [
                        (month, *values)
                        for month, values in quality.items()
                    ]
                elif 'HAVING COUNT(*) > 1' in statement:
                    self.rows = [(0,)]
                else:
                    self.rows = []

            def fetchall(self):
                rows, self.rows = self.rows, []
                return rows

            def fetchone(self):
                rows, self.rows = self.rows, []
                return rows[0] if rows else None

            def executemany(self, _statement, _rows):
                return None

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.committed = False
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                self.committed = True

            def rollback(self):
                raise AssertionError('valid staging load should not roll back')

            def close(self):
                self.closed = True

        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / 'df_ouro.parquet'
            gold.to_parquet(path, index=False)
            connection = Connection()
            with patch.object(
                oracle_upload,
                'con_sql',
                return_value=(connection, 'connected'),
            ):
                oracle_upload.load_staging_parquets(
                    {'ouro': ('OURO_STG', path)},
                    batch_size=1,
                    read_batch_size=1,
                )

        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertIn('TRUNCATE TABLE OURO_STG', connection.cursor_instance.statements)
        self.assertFalse(
            any('TRUNCATE TABLE OURO\n' in query for query in connection.cursor_instance.statements)
        )

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
                        [
                            '2023-01-03',
                            '2025-01-03',
                            '2025-01-12',
                            '2025-01-20',
                            '2099-01-01',
                        ]
                    ),
                    'ID_MUNICIP': pd.Series(
                        [355030] * 5, dtype='Int64'
                    ),
                    'UF': ['35'] * 5,
                    'MUNICIPIO': ['Sao Paulo'] * 5,
                    'CLASSI_FIN': [
                        'dengue', 'dengue', 'descartado',
                        'dengue_grave', 'dengue',
                    ],
                    'EVOLUCAO': ['cura', None, 'obito_dengue', None, None],
                    'HOSPITALIZ': ['2', '1', '2', '2', '1'],
                    'NDUPLIC_N': [None, None, None, 2, None],
                }
            ).to_parquet(input_path, index=False)

            with patch.object(gerar_gold, 'RAW', directory):
                result = gerar_gold.gold_acumulado_municipio(
                    input_path=input_path,
                    output_path=output_path,
                    as_of=pd.Timestamp('2026-10-19'),
                    batch_size=2,
                )

            self.assertEqual(len(result), 2)
            self.assertFalse(
                result.duplicated(['MES_REFERENCIA', 'ID_MUNICIP']).any()
            )
            row_2023 = result.loc[
                result['MES_REFERENCIA'].eq(pd.Timestamp('2023-01-01'))
            ].iloc[0]
            self.assertEqual(int(row_2023['NOTIFICACOES']), 1)
            self.assertEqual(int(row_2023['CASOS_DENGUE']), 1)
            row_2025 = result.loc[
                result['MES_REFERENCIA'].eq(pd.Timestamp('2025-01-01'))
            ].iloc[0]
            self.assertEqual(row_2025['MUNICIPIO'], 'Sao Paulo')
            self.assertEqual(row_2025['UF'], '35')
            self.assertEqual(int(row_2025['NOTIFICACOES']), 2)
            self.assertEqual(int(row_2025['CASOS_DENGUE']), 1)
            self.assertEqual(int(row_2025['OBITOS_DENGUE']), 1)
            self.assertEqual(int(row_2025['HOSPITALIZACOES']), 1)


if __name__ == '__main__':
    unittest.main()
