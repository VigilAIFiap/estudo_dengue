from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import etl
import oracle_upload
import read_data_bronze


class EtlTests(unittest.TestCase):
    def test_etl_merges_years_and_uses_documented_code_mappings(self):
        frames = (
            pd.DataFrame(
                {
                    'DT_NOTIFIC': ['2023-01-04'],
                    'DT_SIN_PRI': ['2023-01-02'],
                    'DT_INVEST': ['2023-01-06'],
                    'ID_MUNICIP': [355030],
                    'MUNICIPIO': ['355030'],
                    'SG_UF_NOT': ['SP'],
                    'CS_ESCOL_N': [0],
                    'CLASSI_FIN': [10],
                    'EVOLUCAO': [4],
                    'NDUPLIC_N': [2],
                    'NU_IDADE_N': [4010],
                    'CS_RACA': [9],
                }
            ),
            pd.DataFrame(
                {
                    'DT_NOTIFIC': ['2024-02-04'],
                    'ID_MUNICIP': [355030],
                    'CS_ESCOL_N': [2],
                    'CLASSI_FIN': [11],
                    'EVOLUCAO': [9],
                }
            ),
            pd.DataFrame(
                {
                    'DT_NOTIFIC': ['2025-03-04'],
                    'ID_MUNICIP': [355030],
                    'CS_ESCOL_N': [3],
                    'CLASSI_FIN': [12],
                    'EVOLUCAO': [2],
                }
            ),
            pd.DataFrame(
                {
                    'DT_NOTIFIC': ['2026-04-04'],
                    'ID_MUNICIP': [355030],
                    'CS_ESCOL_N': [10],
                    'CLASSI_FIN': [8],
                    'EVOLUCAO': [1],
                }
            ),
        )
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            municipalities = directory / 'municipios.csv'
            municipalities.write_text(
                'codigo_ibge,nome,codigo_uf,latitude,longitude,capital\n'
                '3550308,Sao Paulo,35,-23.55,-46.63,1\n',
                encoding='utf-8',
            )
            output = directory / 'processed' / 'prata.parquet'
            result = etl.etl(
                bronze_data=frames,
                municipalities_path=municipalities,
                output_path=output,
            )

            self.assertEqual(len(result), 4)
            self.assertEqual(result['CLASSI_FIN'].tolist(), [
                'dengue',
                'dengue_com_sinais_de_alarme',
                'dengue_grave',
                'inconclusivo',
            ])
            self.assertEqual(result['EVOLUCAO'].iloc[0], 'obito_em_investigacao')
            self.assertEqual(result['CS_ESCOL_N'].tolist(), [
                'analfabeto',
                'quarta_serie_completa',
                'fundamental_incompleto_5a8',
                'nao_se_aplica',
            ])
            self.assertEqual(result['NDUPLIC_N'].iloc[0], 2)
            self.assertEqual(result['CS_RACA'].iloc[0], 'Ignorado')
            self.assertEqual(result['MUNICIPIO'].iloc[0], 'Sao Paulo')
            self.assertEqual(result['UF'].iloc[0], '35')
            self.assertEqual(result['IDADE_ANOS'].iloc[0], 10)
            self.assertEqual(result['NU_IDADE_N'].iloc[0], 4010)
            self.assertNotIn('IDADE_TIPO', result.columns)
            self.assertNotIn('IDADE_VALOR', result.columns)
            self.assertTrue(output.is_file())
            self.assertEqual(oracle_upload.review_dataframe('prata', result), [])

    def test_etl_requires_all_four_cached_bronze_files(self):
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(FileNotFoundError, 'read_data_bronze.py'):
                etl.etl(input_dir=Path(temporary_directory))

    def test_reader_uses_full_2023_2024_csv_and_oracle_2025_2026(self):
        class Cursor:
            description = [('QUERY',)]

            def __init__(self):
                self.rows = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query):
                self.rows = [(query,)]

            def fetchmany(self, _size):
                rows, self.rows = self.rows, []
                return rows

        class Connection:
            closed = False

            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        connection = Connection()
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_2023 = directory / 'DENGBR23.csv'
            source_2023.write_text(
                'DT_NOTIFIC,NU_ANO\n'
                '2023-01-01,2023\n'
                '2023-01-02,2023\n'
                '2024-01-01,2024\n',
                encoding='utf-8',
            )
            source_2024 = directory / 'DENGBR24.csv'
            source_2024.write_text(
                'DT_NOTIFIC,NU_ANO\n'
                '2024-01-01,2024\n'
                '2024-01-02,2024\n'
                '2023-12-31,2023\n',
                encoding='utf-8',
            )
            with (
                patch.object(
                    read_data_bronze,
                    'CSV_SOURCES',
                    {23: source_2023, 24: source_2024},
                ),
                patch.object(read_data_bronze, 'PROCESSED', directory / 'processed'),
                patch.object(
                    read_data_bronze, 'con_sql',
                    return_value=(connection, 'connected'),
                ),
            ):
                counts = read_data_bronze.read_data()

            self.assertTrue(connection.closed)
            self.assertEqual(counts, {23: 2, 24: 2, 25: 1, 26: 1})
            self.assertEqual(
                connection.cursor_instance.description[0][0],
                'QUERY',
            )
            self.assertTrue(
                all(
                    (directory / 'processed' / f'df_bronze_{year}.parquet').is_file()
                    for year in (23, 24, 25, 26)
                )
            )
            saved_23 = pd.read_parquet(
                directory / 'processed' / 'df_bronze_23.parquet'
            )
            self.assertEqual(len(saved_23), 2)
            self.assertEqual(set(saved_23['NU_ANO']), {'2023'})
            saved_24 = pd.read_parquet(
                directory / 'processed' / 'df_bronze_24.parquet'
            )
            self.assertEqual(len(saved_24), 2)
            self.assertEqual(set(saved_24['NU_ANO']), {'2024'})

    def test_oracle_reader_closes_connection_when_query_fails(self):
        class Connection:
            closed = False

            class Cursor:
                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return False

                def execute(self, _query):
                    raise RuntimeError('query failed')

            def cursor(self):
                return self.Cursor()

            def close(self):
                self.closed = True

        connection = Connection()
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_2023 = directory / 'DENGBR23.csv'
            source_2023.write_text(
                'DT_NOTIFIC,NU_ANO\n2023-01-01,2023\n',
                encoding='utf-8',
            )
            source_2024 = directory / 'DENGBR24.csv'
            source_2024.write_text(
                'DT_NOTIFIC,NU_ANO\n2024-01-01,2024\n',
                encoding='utf-8',
            )
            with (
                patch.object(
                    read_data_bronze,
                    'CSV_SOURCES',
                    {23: source_2023, 24: source_2024},
                ),
                patch.object(read_data_bronze, 'PROCESSED', directory / 'processed'),
                patch.object(
                    read_data_bronze, 'con_sql',
                    return_value=(connection, 'connected'),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, 'query failed'):
                    read_data_bronze.read_data()
        self.assertTrue(connection.closed)


if __name__ == '__main__':
    unittest.main()
