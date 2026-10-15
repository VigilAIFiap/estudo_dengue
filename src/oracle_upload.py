from __future__ import annotations

import argparse
import os
import re
from itertools import islice

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from config import DADOS
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
            'DT_NOTIFIC', 'ID_MUNICIP', 'UF', 'MUNICIPIO', 'codigo_ibge',
        }
        missing = sorted(required.difference(df.columns))
        if missing:
            blockers.append(f'colunas esperadas ausentes: {missing}')
        elif df['MUNICIPIO'].isna().all() or df['codigo_ibge'].isna().all():
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


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description='Revisa e substitui dados das camadas Prata e Ouro no Oracle.'
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
        '--review-only',
        action='store_true',
        help='Executa somente a revisão local, sem conectar ao Oracle.',
    )
    args = parser.parse_args()

    selected = list(LAYERS) if args.layer == 'all' else [args.layer]
    target_names = {
        'prata': args.table_prata,
        'ouro': args.table_ouro,
    }
    loaded_layers = {}
    blockers = []
    for layer in selected:
        filename, _ = LAYERS[layer]
        path = DADOS / filename
        if not path.is_file():
            raise FileNotFoundError(
                f'Arquivo da camada {layer} não encontrado: {path}. '
                f'Gere-o antes de executar a carga.'
            )
        df = pd.read_parquet(path)
        blockers.extend(
            f'{layer}: {blocker}'
            for blocker in review_dataframe(layer, df)
        )
        loaded_layers[layer] = (target_names[layer], df)

    if args.review_only:
        print('\nRevisão concluída; nenhuma conexão Oracle foi aberta.')
        return
    if blockers:
        raise ValueError(
            'Carga cancelada até corrigir os bloqueios: ' + '; '.join(blockers)
        )

    replace_tables(loaded_layers, batch_size=args.batch_size)


if __name__ == '__main__':
    main()
