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

    def test_chunked_silver_etl_matches_full_dataframe_transformation(self):
        frames = tuple(
            pd.DataFrame(
                {
                    'DT_NOTIFIC': [f'20{year}-01-04', f'20{year}-01-05'],
                    'ID_MUNICIP': [355030, 355030],
                    'CLASSI_FIN': [10, 12],
                    'EVOLUCAO': [1, 2],
                    'HOSPITALIZ': [1, 2],
                    **(
                        {'NU_IDADE_N': [4010, 4020]}
                        if year in (23, 25)
                        else {}
                    ),
                }
            )
            for year in (23, 24, 25, 26)
        )
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            municipalities = directory / 'municipios.csv'
            municipalities.write_text(
                'codigo_ibge,nome,codigo_uf,latitude,longitude,capital\n'
                '3550308,Sao Paulo,35,-23.55,-46.63,1\n',
                encoding='utf-8',
            )
            input_dir = directory / 'processed'
            input_dir.mkdir()
            for year, frame in zip((23, 24, 25, 26), frames):
                frame.to_parquet(
                    input_dir / f'df_bronze_{year}.parquet',
                    index=False,
                )
            expected = etl.etl(
                bronze_data=frames,
                municipalities_path=municipalities,
                output_path=directory / 'expected.parquet',
            )
            count = etl.etl_parquet_batches(
                input_dir=input_dir,
                municipalities_path=municipalities,
                output_path=directory / 'streamed.parquet',
                batch_size=1,
            )
            actual = pd.read_parquet(directory / 'streamed.parquet')

        self.assertEqual(count, 8)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)

    def test_reader_uses_all_four_local_annual_csvs(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            sources = {}
            for year in (23, 24, 25, 26):
                source = directory / f'DENGBR{year}.csv'
                other_date, other_year = (
                    ('2024-12-31', '2024')
                    if year == 23
                    else ('2023-12-31', '2023')
                )
                source.write_text(
                    'DT_NOTIFIC,NU_ANO\n'
                    f'20{year}-01-01,20{year}\n'
                    f'20{year}-01-02,20{year}\n'
                    f'{other_date},{other_year}\n',
                    encoding='utf-8',
                )
                sources[year] = source
            with (
                patch.object(
                    read_data_bronze,
                    'CSV_SOURCES',
                    sources,
                ),
                patch.object(read_data_bronze, 'PROCESSED', directory / 'processed'),
            ):
                counts = read_data_bronze.read_data()

            self.assertEqual(counts, {23: 2, 24: 2, 25: 2, 26: 2})
            self.assertTrue(
                all(
                    (directory / 'processed' / f'df_bronze_{year}.parquet').is_file()
                    for year in (23, 24, 25, 26)
                )
            )
            for year in (23, 24, 25, 26):
                saved = pd.read_parquet(
                    directory / 'processed' / f'df_bronze_{year}.parquet'
                )
                self.assertEqual(len(saved), 2)
                self.assertEqual(set(saved['NU_ANO']), {f'20{year}'})

    def test_reader_preserves_existing_parquets_if_a_source_is_missing(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            processed = directory / 'processed'
            processed.mkdir()
            for year in (23, 24, 25, 26):
                (processed / f'df_bronze_{year}.parquet').write_bytes(
                    f'old-{year}'.encode()
                )
            sources = {}
            for year in (23, 24, 25):
                source = directory / f'DENGBR{year}.csv'
                source.write_text(
                    'DT_NOTIFIC,NU_ANO\n'
                    f'20{year}-01-01,20{year}\n',
                    encoding='utf-8',
                )
                sources[year] = source
            sources[26] = directory / 'missing.csv'
            with (
                patch.object(read_data_bronze, 'CSV_SOURCES', sources),
                patch.object(read_data_bronze, 'PROCESSED', processed),
            ):
                with self.assertRaisesRegex(FileNotFoundError, 'Fontes CSV'):
                    read_data_bronze.read_data()
            for year in (23, 24, 25, 26):
                self.assertEqual(
                    (processed / f'df_bronze_{year}.parquet').read_bytes(),
                    f'old-{year}'.encode(),
                )

    def test_staging_loader_validates_monthly_values_without_touching_production(self):
        prata = pd.DataFrame(
            {
                'DT_NOTIFIC': pd.to_datetime(
                    ['2025-01-02', '2025-01-15', '2025-02-01']
                ),
                'ID_MUNICIP': [355030, 355030, 110020],
                'UF': ['35', '35', '11'],
                'MUNICIPIO': ['Sao Paulo', 'Sao Paulo', 'Porto Velho'],
                'CODIGO_IBGE': [3550308, 3550308, 1100205],
                'CLASSI_FIN': ['dengue', 'descartado', 'dengue_grave'],
                'EVOLUCAO': ['obito_dengue', 'cura', 'cura'],
                'HOSPITALIZ': [1, 2, 1],
            }
        )
        ouro = pd.DataFrame(
            {
                'MES_REFERENCIA': pd.to_datetime(
                    ['2025-01-01', '2025-02-01']
                ),
                'ID_MUNICIP': [355030, 110020],
                'UF': ['35', '11'],
                'MUNICIPIO': ['Sao Paulo', 'Porto Velho'],
                'NOTIFICACOES': [2, 1],
                'CASOS_DENGUE': [1, 1],
                'OBITOS_DENGUE': [1, 0],
                'HOSPITALIZACOES': [1, 1],
            }
        )

        class Cursor:
            def __init__(self):
                self.rows = []
                self.executed = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, **binds):
                self.executed.append(query)
                if 'FROM user_tab_columns' in query:
                    name = binds['table_name']
                    frame = {'PRATA_STG': prata, 'OURO_STG': ouro}[name]
                    self.rows = [
                        (str(column).upper(), 'Y', None)
                        for column in frame.columns
                    ]
                elif query.startswith('SELECT COUNT(*) FROM PRATA_STG'):
                    self.rows = [(len(prata),)]
                elif query.startswith('SELECT COUNT(*) FROM OURO_STG'):
                    self.rows = [(len(ouro),)]
                elif 'GROUP BY TRUNC(DT_NOTIFIC' in query:
                    quality = oracle_upload._expected_monthly_quality(
                        'prata', prata
                    )
                    self.rows = [(month, *values) for month, values in quality.items()]
                elif 'GROUP BY TRUNC(MES_REFERENCIA' in query:
                    quality = oracle_upload._expected_monthly_quality('ouro', ouro)
                    self.rows = [(month, *values) for month, values in quality.items()]
                elif 'HAVING COUNT(*) > 1' in query:
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

        connection = Connection()
        with patch.object(
            oracle_upload,
            'con_sql',
            return_value=(connection, 'connected'),
        ):
            oracle_upload.load_staging_tables(
                {
                    'prata': ('PRATA_STG', prata),
                    'ouro': ('OURO_STG', ouro),
                },
                batch_size=2,
            )

        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)
        statements = connection.cursor_instance.executed
        self.assertIn('TRUNCATE TABLE PRATA_STG', statements)
        self.assertIn('TRUNCATE TABLE OURO_STG', statements)
        self.assertFalse(any('TRUNCATE TABLE PRATA\n' == query for query in statements))
        self.assertFalse(any('DELETE FROM PRATA' in query for query in statements))

    def test_staging_loader_rejects_production_table_names_before_connecting(self):
        with patch.object(oracle_upload, 'con_sql') as connect:
            with self.assertRaisesRegex(ValueError, 'terminadas em _STG'):
                oracle_upload.load_staging_tables(
                    {'prata': ('PRATA', pd.DataFrame({'DT_NOTIFIC': ['2025-01-01']}))}
                )
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
