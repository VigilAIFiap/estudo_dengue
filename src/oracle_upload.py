from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from itertools import islice

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from dotenv import load_dotenv

from config import PROCESSED
from con_db import con_sql


LAYERS = {
    'prata': ('df_prata.parquet', 'PRATA'),
    'ouro': ('df_ouro.parquet', 'OURO'),
}


def review_dataframe(layer: str, df: pd.DataFrame) -> list[str]:
    if df.empty:
        raise ValueError(f'A camada {layer} está vazia.')
    if not len(df.columns):
        raise ValueError(f'A camada {layer} não possui colunas.')

    blockers = []
    normalized_columns = [str(column).upper() for column in df.columns]
    duplicate_columns = sorted({
        column for column in normalized_columns
        if normalized_columns.count(column) > 1
    })
    if duplicate_columns:
        blockers.append(f'colunas repetidas no Oracle: {duplicate_columns}')

    if layer == 'prata':
        required = {
            'dt_notific', 'id_municip', 'uf', 'municipio', 'codigo_ibge',
        }
        normalized = {str(column).lower(): column for column in df.columns}
        missing = sorted(required.difference(normalized))
        if missing:
            blockers.append(f'colunas esperadas ausentes: {missing}')
        elif df[normalized['municipio']].isna().all() or df[
            normalized['codigo_ibge']
        ].isna().all():
            blockers.append(
                'vínculo com municípios vazio; regenere a camada com src\\etl.py'
            )

    if layer == 'ouro':
        required = {
            'MES_REFERENCIA', 'ID_MUNICIP', 'UF', 'MUNICIPIO',
            'NOTIFICACOES', 'CASOS_DENGUE', 'OBITOS_DENGUE', 'HOSPITALIZACOES',
        }
        missing = sorted(required.difference(df.columns))
        if missing:
            blockers.append(
                'a Ouro não está agregada no grão mensal por município; '
                'regenere com src\\gerar_gold.py '
                f'(colunas ausentes: {missing})'
            )
        else:
            required_values = [
                'MES_REFERENCIA', 'ID_MUNICIP', 'UF', 'MUNICIPIO',
                'NOTIFICACOES', 'CASOS_DENGUE', 'OBITOS_DENGUE',
                'HOSPITALIZACOES',
            ]
            null_required = [
                column for column in required_values if df[column].isna().any()
            ]
            if null_required:
                blockers.append(
                    f'valores nulos em colunas obrigatórias: {null_required}'
                )

    print(
        f'\n[{layer.upper()}] {len(df):,} linhas; {len(df.columns)} colunas; '
        f'{int(df.duplicated().sum()):,} linhas exatamente duplicadas.'
    )
    null_counts = df.isna().sum()
    null_counts = null_counts[null_counts > 0].sort_values(ascending=False)
    if null_counts.empty:
        print('Nulos: nenhum.')
    else:
        print('Nulos por coluna (quantidade/percentual):')
        for column, count in null_counts.items():
            print(f'  {column}: {int(count):,} ({count / len(df):.1%})')

    for column in df.columns:
        if not str(column).upper().startswith('DT_'):
            continue
        values = pd.to_datetime(df[column], errors='coerce').dropna()
        if values.empty:
            continue
        old_count = int((values < pd.Timestamp('1900-01-01')).sum())
        future_count = int(
            (values > pd.Timestamp.today().normalize()).sum()
        )
        if old_count or future_count:
            print(
                f'  ATENÇÃO {column}: {old_count:,} datas anteriores a 1900; '
                f'{future_count:,} datas futuras.'
            )

    gold_key = {'MES_REFERENCIA', 'ID_MUNICIP'}
    if layer == 'ouro' and gold_key.issubset(df.columns):
        duplicate_keys = int(df.duplicated(sorted(gold_key)).sum())
        print(f'Chaves mensais (mês, ID do município) repetidas: {duplicate_keys:,}.')
        if duplicate_keys:
            print('  ATENÇÃO: a Ouro deveria ter uma linha por mês e município.')
            blockers.append(
                f'{duplicate_keys:,} chaves mensais mês/ID do município repetidas'
            )
    for blocker in blockers:
        print(f'  BLOQUEIO DE CARGA: {blocker}.')
    return blockers


def review_parquet(
    layer: str,
    path,
    batch_size: int = 25_000,
) -> list[str]:
    parquet = pq.ParquetFile(path)
    try:
        row_count = parquet.metadata.num_rows
        columns = parquet.schema_arrow.names
    finally:
        parquet.close()
    normalized_columns = [str(column).upper() for column in columns]
    duplicate_columns = sorted({
        column for column in normalized_columns
        if normalized_columns.count(column) > 1
    })
    blockers = []
    if row_count == 0:
        blockers.append(f'a camada {layer} está vazia')
    if duplicate_columns:
        blockers.append(f'colunas repetidas no Oracle: {duplicate_columns}')

    normalized = {str(column).lower(): column for column in columns}
    if layer == 'prata':
        required = {
            'dt_notific', 'id_municip', 'uf', 'municipio', 'codigo_ibge',
        }
        missing = sorted(required.difference(normalized))
        if missing:
            blockers.append(f'colunas esperadas ausentes: {missing}')
    elif layer == 'ouro':
        required = {
            'MES_REFERENCIA', 'ID_MUNICIP', 'UF', 'MUNICIPIO',
            'NOTIFICACOES', 'CASOS_DENGUE', 'OBITOS_DENGUE', 'HOSPITALIZACOES',
        }
        missing = sorted(required.difference(columns))
        if missing:
            blockers.append(
                'a Ouro não está agregada no grão mensal por município; '
                f'colunas ausentes: {missing}'
            )
    else:
        raise ValueError(f'Camada desconhecida: {layer}')

    null_counts = defaultdict(int)
    date_issues = defaultdict(lambda: [0, 0])
    exact_duplicates_in_batch = 0
    seen_gold_keys = set()
    duplicate_gold_keys = 0
    parquet = pq.ParquetFile(path)
    try:
        for batch in parquet.iter_batches(batch_size=batch_size):
            frame = batch.to_pandas()
            exact_duplicates_in_batch += int(frame.duplicated().sum())
            counts = frame.isna().sum()
            for column, count in counts.items():
                null_counts[str(column)] += int(count)
            for column in frame.columns:
                if not str(column).upper().startswith('DT_'):
                    continue
                values = pd.to_datetime(frame[column], errors='coerce').dropna()
                if not values.empty:
                    date_issues[str(column)][0] += int(
                        values.lt(pd.Timestamp('1900-01-01')).sum()
                    )
                    date_issues[str(column)][1] += int(
                        values.gt(pd.Timestamp.today().normalize()).sum()
                    )
            if layer == 'ouro' and {'MES_REFERENCIA', 'ID_MUNICIP'}.issubset(frame):
                months = pd.to_datetime(
                    frame['MES_REFERENCIA'], errors='coerce'
                ).dt.normalize()
                for month, municipality in zip(months, frame['ID_MUNICIP']):
                    key = (
                        None if pd.isna(month) else month,
                        None if pd.isna(municipality) else int(municipality),
                    )
                    if key in seen_gold_keys:
                        duplicate_gold_keys += 1
                    else:
                        seen_gold_keys.add(key)
    finally:
        parquet.close()

    print(
        f'\n[{layer.upper()}] {row_count:,} linhas; {len(columns)} colunas; '
        f'{exact_duplicates_in_batch:,} duplicatas exatas detectadas dentro '
        'dos lotes (duplicatas entre lotes não são contadas).'
    )
    nonzero_nulls = sorted(
        ((column, count) for column, count in null_counts.items() if count),
        key=lambda item: item[1],
        reverse=True,
    )
    if not nonzero_nulls:
        print('Nulos: nenhum.')
    else:
        print('Nulos por coluna (quantidade/percentual):')
        for column, count in nonzero_nulls:
            print(f'  {column}: {count:,} ({count / row_count:.1%})')
    for column, (old_count, future_count) in date_issues.items():
        if old_count or future_count:
            print(
                f'  ATENÇÃO {column}: {old_count:,} datas anteriores a 1900; '
                f'{future_count:,} datas futuras.'
            )
    if layer == 'ouro':
        print(
            'Chaves mensais (mês, ID do município) repetidas: '
            f'{duplicate_gold_keys:,}.'
        )
        if duplicate_gold_keys:
            blockers.append(
                f'{duplicate_gold_keys:,} chaves mensais mês/ID do município repetidas'
            )
        null_required = [
            column
            for column in (
                'MES_REFERENCIA', 'ID_MUNICIP', 'UF', 'MUNICIPIO',
                'NOTIFICACOES', 'CASOS_DENGUE', 'OBITOS_DENGUE',
                'HOSPITALIZACOES',
            )
            if column in null_counts and null_counts[column]
        ]
        if null_required:
            blockers.append(
                f'valores nulos em colunas obrigatórias: {null_required}'
            )
    if layer == 'prata' and 'municipio' in normalized and 'codigo_ibge' in normalized:
        if null_counts[normalized['municipio']] == row_count or (
            null_counts[normalized['codigo_ibge']] == row_count
        ):
            blockers.append('vínculo com municípios vazio')

    for blocker in blockers:
        print(f'  BLOQUEIO DE CARGA: {blocker}.')
    return blockers


def _normalize_value(value):
    if not pd.api.types.is_scalar(value):
        raise TypeError(f'Valor não escalar não pode ser enviado ao Oracle: {type(value).__name__}')
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return int(value)
    return value


def _validate_table_name(table_name: str) -> str:
    name = table_name.upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}', name):
        raise ValueError(f'Nome de tabela Oracle inválido: {table_name!r}')
    return name


def _validate_staging_table_name(table_name: str) -> str:
    name = _validate_table_name(table_name)
    if not name.endswith('_STG'):
        raise ValueError(
            f'A carga de preparação só aceita tabelas terminadas em _STG: {name}'
        )
    return name


def _validate_table_columns(cursor, table_name: str, df: pd.DataFrame) -> None:
    cursor.execute(
        '''
        SELECT column_name, nullable, data_default
        FROM user_tab_columns
        WHERE table_name = :table_name
        ''',
        table_name=table_name,
    )
    table_columns = {
        name.upper(): (nullable, default)
        for name, nullable, default in cursor.fetchall()
    }
    if not table_columns:
        raise ValueError(
            f'A tabela {table_name} não existe no schema do usuário conectado.'
        )

    missing = sorted(
        str(column).upper()
        for column in df.columns
        if str(column).upper() not in table_columns
    )
    if missing:
        raise ValueError(
            f'A tabela {table_name} não possui colunas da camada: {missing}'
        )

    extra_required = sorted(
        column for column, (nullable, default) in table_columns.items()
        if column not in {str(c).upper() for c in df.columns}
        and nullable == 'N'
        and default is None
    )
    if extra_required:
        raise ValueError(
            f'A tabela {table_name} exige colunas que não existem na camada '
            f'e não têm valor padrão: {extra_required}'
        )


def _expected_monthly_quality(layer: str, df: pd.DataFrame) -> dict:
    if layer == 'prata':
        dates = pd.to_datetime(df['DT_NOTIFIC'], errors='coerce')
        classification = df['CLASSI_FIN'].astype('string').str.lower()
        evolution = df['EVOLUCAO'].astype('string').str.lower()
        hospitalization = pd.to_numeric(
            df['HOSPITALIZ'], errors='coerce'
        ).eq(1)
        frame = pd.DataFrame(
            {
                'month': dates.dt.to_period('M').dt.to_timestamp(),
                'cases': classification.isin(
                    ['dengue', 'dengue_com_sinais_de_alarme', 'dengue_grave']
                ).astype('int64'),
                'deaths': evolution.eq('obito_dengue').fillna(False).astype('int64'),
                'hospitalizations': hospitalization.fillna(False).astype('int64'),
            }
        )
        grouped = frame.groupby('month', dropna=False).agg(
            rows=('cases', 'size'),
            cases=('cases', 'sum'),
            deaths=('deaths', 'sum'),
            hospitalizations=('hospitalizations', 'sum'),
        )
    elif layer == 'ouro':
        frame = df.copy()
        frame['month'] = pd.to_datetime(
            frame['MES_REFERENCIA'], errors='coerce'
        ).dt.to_period('M').dt.to_timestamp()
        grouped = frame.groupby('month', dropna=False).agg(
            rows=('ID_MUNICIP', 'size'),
            cases=('CASOS_DENGUE', 'sum'),
            deaths=('OBITOS_DENGUE', 'sum'),
            hospitalizations=('HOSPITALIZACOES', 'sum'),
        )
        grouped['notifications'] = frame.groupby(
            'month', dropna=False
        )['NOTIFICACOES'].sum()
    else:
        raise ValueError(f'Camada desconhecida: {layer}')

    result = {}
    for month, row in grouped.iterrows():
        month_key = None if pd.isna(month) else pd.Timestamp(month).normalize()
        result[month_key] = tuple(int(row[key]) for key in (
            'rows', 'cases', 'deaths', 'hospitalizations'
        )) + (
            (int(row['notifications']),) if layer == 'ouro' else ()
        )
    return result


def _validate_staging_content(
    cursor,
    layer: str,
    table_name: str,
    df: pd.DataFrame,
) -> None:
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    actual_rows = int(cursor.fetchone()[0])
    if actual_rows != len(df):
        raise ValueError(
            f'{table_name} contém {actual_rows:,} linhas; '
            f'o Parquet de {layer} contém {len(df):,}.'
        )

    if layer == 'prata':
        cursor.execute(
            f'''
            SELECT TRUNC(DT_NOTIFIC, 'MM'),
                   COUNT(*),
                   SUM(CASE WHEN CLASSI_FIN IN (
                       'dengue', 'dengue_com_sinais_de_alarme', 'dengue_grave'
                   ) THEN 1 ELSE 0 END),
                   SUM(CASE WHEN EVOLUCAO = 'obito_dengue' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN HOSPITALIZ = 1 THEN 1 ELSE 0 END)
            FROM {table_name}
            GROUP BY TRUNC(DT_NOTIFIC, 'MM')
            '''
        )
    elif layer == 'ouro':
        cursor.execute(
            f'''
            SELECT TRUNC(MES_REFERENCIA, 'MM'),
                   COUNT(*),
                   SUM(CASOS_DENGUE),
                   SUM(OBITOS_DENGUE),
                   SUM(HOSPITALIZACOES),
                   SUM(NOTIFICACOES)
            FROM {table_name}
            GROUP BY TRUNC(MES_REFERENCIA, 'MM')
            '''
        )
        actual = cursor.fetchall()
        cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM (
                SELECT MES_REFERENCIA, ID_MUNICIP
                FROM {table_name}
                GROUP BY MES_REFERENCIA, ID_MUNICIP
                HAVING COUNT(*) > 1
            )
            '''
        )
        duplicate_keys = int(cursor.fetchone()[0])
        if duplicate_keys:
            raise ValueError(
                f'{table_name} contém {duplicate_keys:,} chaves mensais '
                'duplicadas (MES_REFERENCIA, ID_MUNICIP).'
            )
        expected = _expected_monthly_quality(layer, df)
        normalized = {
            None if month is None else pd.Timestamp(month).normalize(): tuple(
                int(value) for value in values
            )
            for month, *values in actual
        }
        if normalized != expected:
            raise ValueError(
                f'Agregados mensais de {table_name} divergem do Parquet Ouro.'
            )
        return
    else:
        raise ValueError(f'Camada desconhecida: {layer}')

    actual = cursor.fetchall()
    normalized = {
        None if month is None else pd.Timestamp(month).normalize(): tuple(
            int(value) for value in values
        )
        for month, *values in actual
    }
    expected = _expected_monthly_quality(layer, df)
    if normalized != expected:
        raise ValueError(
            f'Contagens e métricas mensais de {table_name} divergem do '
            f'Parquet {layer.capitalize()}.'
        )


def _merge_monthly_quality(target: dict, layer: str, frame: pd.DataFrame) -> None:
    for month, values in _expected_monthly_quality(layer, frame).items():
        previous = target.get(month, tuple(0 for _ in values))
        target[month] = tuple(
            left + right for left, right in zip(previous, values)
        )


def _oracle_monthly_quality(cursor, layer: str, table_name: str) -> dict:
    if layer == 'prata':
        query = f'''
            SELECT TRUNC(DT_NOTIFIC, 'MM'),
                   COUNT(*),
                   SUM(CASE WHEN CLASSI_FIN IN (
                       'dengue', 'dengue_com_sinais_de_alarme', 'dengue_grave'
                   ) THEN 1 ELSE 0 END),
                   SUM(CASE WHEN EVOLUCAO = 'obito_dengue' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN HOSPITALIZ = 1 THEN 1 ELSE 0 END)
            FROM {table_name}
            GROUP BY TRUNC(DT_NOTIFIC, 'MM')
        '''
    else:
        query = f'''
            SELECT TRUNC(MES_REFERENCIA, 'MM'),
                   COUNT(*),
                   SUM(CASOS_DENGUE),
                   SUM(OBITOS_DENGUE),
                   SUM(HOSPITALIZACOES),
                   SUM(NOTIFICACOES)
            FROM {table_name}
            GROUP BY TRUNC(MES_REFERENCIA, 'MM')
        '''
    cursor.execute(query)
    rows = cursor.fetchall()
    result = {
        None if month is None else pd.Timestamp(month).normalize(): tuple(
            int(value) for value in values
        )
        for month, *values in rows
    }
    if layer == 'ouro':
        cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM (
                SELECT MES_REFERENCIA, ID_MUNICIP
                FROM {table_name}
                GROUP BY MES_REFERENCIA, ID_MUNICIP
                HAVING COUNT(*) > 1
            )
            '''
        )
        duplicates = int(cursor.fetchone()[0])
        if duplicates:
            raise ValueError(
                f'{table_name} contém {duplicates:,} chaves mensais '
                'duplicadas (MES_REFERENCIA, ID_MUNICIP).'
            )
    return result


def load_staging_parquets(
    layers: dict[str, tuple[str, object]],
    batch_size: int = 1000,
    read_batch_size: int = 25_000,
) -> None:
    if batch_size < 1 or read_batch_size < 1:
        raise ValueError('Os tamanhos dos lotes devem ser maiores que zero.')
    tables = {
        layer: (_validate_staging_table_name(table_name), path)
        for layer, (table_name, path) in layers.items()
    }
    signatures = {
        layer: (os.stat(path).st_size, os.stat(path).st_mtime_ns)
        for layer, (_, path) in tables.items()
    }
    expected_rows = {}
    for layer, (_, path) in tables.items():
        blockers = review_parquet(layer, path, batch_size=read_batch_size)
        if blockers:
            raise ValueError(
                f'Carga em staging cancelada para {layer}: '
                + '; '.join(blockers)
            )
        parquet = pq.ParquetFile(path)
        try:
            expected_rows[layer] = parquet.metadata.num_rows
        finally:
            parquet.close()

    conn, status = con_sql()
    if conn is None:
        raise RuntimeError(f'Não foi possível conectar ao Oracle: {status}')
    try:
        with conn.cursor() as cursor:
            cursor.execute('ALTER SESSION DISABLE PARALLEL DML')
            for layer, (table_name, path) in tables.items():
                parquet = pq.ParquetFile(path)
                try:
                    first_batch = next(parquet.iter_batches(batch_size=1), None)
                finally:
                    parquet.close()
                if first_batch is None:
                    raise ValueError(f'O Parquet de {layer} está vazio.')
                _validate_table_columns(
                    cursor,
                    table_name,
                    first_batch.to_pandas(),
                )

            for table_name, _ in tables.values():
                cursor.execute(f'TRUNCATE TABLE {table_name}')

            for layer, (table_name, path) in tables.items():
                parquet = pq.ParquetFile(path)
                expected_quality = {}
                inserted = 0
                try:
                    for batch in parquet.iter_batches(
                        batch_size=read_batch_size,
                    ):
                        frame = batch.to_pandas()
                        _merge_monthly_quality(
                            expected_quality,
                            layer,
                            frame,
                        )
                        _insert_dataframe(
                            cursor,
                            table_name,
                            frame,
                            batch_size,
                        )
                        inserted += len(frame)
                finally:
                    parquet.close()
                if inserted != expected_rows[layer]:
                    raise ValueError(
                        f'Parquet de {layer} mudou durante a carga: esperado '
                        f'{expected_rows[layer]:,}, lido {inserted:,}.'
                    )

                cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
                actual_rows = int(cursor.fetchone()[0])
                if actual_rows != expected_rows[layer]:
                    raise ValueError(
                        f'{table_name} contém {actual_rows:,} linhas; '
                        f'o Parquet de {layer} contém {expected_rows[layer]:,}.'
                    )
                actual_quality = _oracle_monthly_quality(
                    cursor,
                    layer,
                    table_name,
                )
                if actual_quality != expected_quality:
                    raise ValueError(
                        f'Contagens e métricas mensais de {table_name} divergem '
                        f'do Parquet {layer.capitalize()}.'
                    )
                print(
                    f'  {table_name}: {inserted:,} linhas; contagem e '
                    'agregados mensais conferidos.'
                )
            changed_layers = [
                layer
                for layer, (_, path) in tables.items()
                if (os.stat(path).st_size, os.stat(path).st_mtime_ns)
                != signatures[layer]
            ]
            if changed_layers:
                raise RuntimeError(
                    'Parquets foram modificados durante a carga em staging: '
                    + ', '.join(changed_layers)
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        'Carga em staging concluída e validada; PRATA e OURO de produção '
        'não foram alteradas.'
    )


def _insert_dataframe(cursor, table_name: str, df: pd.DataFrame, batch_size: int) -> None:
    columns = [str(column).upper() for column in df.columns]
    quoted_columns = ', '.join(f'"{column}"' for column in columns)
    binds = ', '.join(f':{index}' for index in range(1, len(columns) + 1))
    statement = (
        f'INSERT INTO {table_name} ({quoted_columns}) VALUES ({binds})'
    )

    rows = df.itertuples(index=False, name=None)
    inserted = 0
    while True:
        batch = list(islice(rows, batch_size))
        if not batch:
            break
        normalized_batch = [
            tuple(_normalize_value(value) for value in row)
            for row in batch
        ]
        cursor.executemany(statement, normalized_batch)
        inserted += len(normalized_batch)
    print(f'  {table_name}: {inserted:,} linhas preparadas para carga.')


def replace_tables(layers: dict[str, tuple[str, pd.DataFrame]], batch_size: int = 1000) -> None:
    if batch_size < 1:
        raise ValueError('O tamanho do lote deve ser maior que zero.')

    tables = {
        _validate_table_name(table_name): df
        for table_name, df in layers.values()
    }
    conn, status = con_sql()
    if conn is None:
        raise RuntimeError(f'Não foi possível conectar ao Oracle: {status}')

    try:
        with conn.cursor() as cursor:
            cursor.execute('ALTER SESSION DISABLE PARALLEL DML')
            for table_name, df in tables.items():
                _validate_table_columns(cursor, table_name, df)

            for table_name in tables:
                cursor.execute(f'DELETE FROM {table_name}')
            for table_name, df in tables.items():
                _insert_dataframe(cursor, table_name, df, batch_size)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print('Substituição concluída e confirmada no Oracle.')


def load_staging_tables(
    layers: dict[str, tuple[str, pd.DataFrame]],
    batch_size: int = 1000,
) -> None:
    if batch_size < 1:
        raise ValueError('O tamanho do lote deve ser maior que zero.')

    tables = {
        layer: (_validate_staging_table_name(table_name), df)
        for layer, (table_name, df) in layers.items()
    }
    conn, status = con_sql()
    if conn is None:
        raise RuntimeError(f'Não foi possível conectar ao Oracle: {status}')

    try:
        with conn.cursor() as cursor:
            cursor.execute('ALTER SESSION DISABLE PARALLEL DML')
            for table_name, df in tables.values():
                _validate_table_columns(cursor, table_name, df)

            for table_name, _ in tables.values():
                cursor.execute(f'TRUNCATE TABLE {table_name}')
            for layer, (table_name, df) in tables.items():
                _insert_dataframe(cursor, table_name, df, batch_size)
                _validate_staging_content(cursor, layer, table_name, df)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        'Carga em staging concluída e validada; PRATA e OURO de produção '
        'não foram alteradas.'
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description='Revisa camadas locais e carrega staging ou substitui tabelas Oracle.'
    )
    parser.add_argument(
        '--layer',
        choices=['prata', 'ouro', 'all'],
        default='all',
        help='Camada a revisar/carregar (padrão: all).',
    )
    parser.add_argument(
        '--table-prata',
        default=os.getenv('ORACLE_TABLE_PRATA', 'PRATA'),
        help='Tabela Oracle da camada Prata.',
    )
    parser.add_argument(
        '--table-ouro',
        default=os.getenv('ORACLE_TABLE_OURO', 'OURO'),
        help='Tabela Oracle da camada Ouro.',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Quantidade de linhas por lote de inserção.',
    )
    parser.add_argument(
        '--mode',
        choices=['staging', 'replace'],
        default='staging',
        help='staging (padrão) preserva produção; replace substitui tabelas finais.',
    )
    parser.add_argument(
        '--confirm-replace',
        action='store_true',
        help='Confirma explicitamente a substituição destrutiva das tabelas finais.',
    )
    parser.add_argument(
        '--review-only',
        action='store_true',
        help='Executa somente a revisão local, sem conectar ao Oracle.',
    )
    args = parser.parse_args()

    if args.mode == 'replace' and not args.confirm_replace:
        parser.error(
            '--mode replace exige --confirm-replace; use staging para preservar '
            'as tabelas atuais.'
        )

    selected = list(LAYERS) if args.layer == 'all' else [args.layer]
    target_names = {
        'prata': (
            f'{args.table_prata}_STG'
            if args.mode == 'staging'
            else args.table_prata
        ),
        'ouro': (
            f'{args.table_ouro}_STG'
            if args.mode == 'staging'
            else args.table_ouro
        ),
    }
    layer_paths = {}
    blockers = []
    for layer in selected:
        filename, _ = LAYERS[layer]
        path = PROCESSED / filename
        if not path.is_file():
            raise FileNotFoundError(
                f'Arquivo da camada {layer} não encontrado: {path}. '
                f'Gere-o antes de executar a carga.'
            )
        layer_paths[layer] = path

    if args.review_only:
        for layer, path in layer_paths.items():
            blockers.extend(
                f'{layer}: {blocker}'
                for blocker in review_parquet(layer, path)
            )
        if blockers:
            raise ValueError(
                'Revisão encontrou bloqueios: ' + '; '.join(blockers)
            )
        print('\nRevisão concluída; nenhuma conexão Oracle foi aberta.')
        return

    if args.mode == 'staging':
        staging_layers = {
            layer: (target_names[layer], path)
            for layer, path in layer_paths.items()
        }
        load_staging_parquets(
            staging_layers,
            batch_size=args.batch_size,
        )
        return

    for layer, path in layer_paths.items():
        blockers.extend(
            f'{layer}: {blocker}'
            for blocker in review_parquet(layer, path)
        )
    if blockers:
        raise ValueError(
            'Carga cancelada até corrigir os bloqueios: ' + '; '.join(blockers)
        )

    loaded_layers = {
        layer: (target_names[layer], pd.read_parquet(path))
        for layer, path in layer_paths.items()
    }
    for layer, (_, df) in loaded_layers.items():
        blockers.extend(
            f'{layer}: {blocker}'
            for blocker in review_dataframe(layer, df)
        )
    if blockers:
        raise ValueError(
            'Carga cancelada até corrigir os bloqueios: ' + '; '.join(blockers)
        )
    replace_tables(loaded_layers, batch_size=args.batch_size)


if __name__ == '__main__':
    main()
