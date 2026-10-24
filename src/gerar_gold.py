from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import PROCESSED, RAW


DENGUE_CLASSIFICATIONS = {
    'dengue',
    'dengue_com_sinais_de_alarme',
    'dengue_grave',
}


def gold_acumulado_municipio(
    input_path=None,
    output_path=None,
    municipalities_path=None,
    as_of=None,
    batch_size=25_000,
):
    input_path = input_path or PROCESSED / 'df_prata.parquet'
    output_path = output_path or PROCESSED / 'df_ouro.parquet'
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f'Parquet Prata não encontrado: {input_path}')
    if batch_size < 1:
        raise ValueError('batch_size deve ser maior que zero.')
    parquet = pq.ParquetFile(input_path)
    try:
        available = set(parquet.schema_arrow.names)
    finally:
        parquet.close()
    required = {'DT_NOTIFIC', 'ID_MUNICIP'}
    missing = required.difference(available)
    if missing:
        raise ValueError(f'Colunas obrigatórias ausentes na Prata: {sorted(missing)}')

    reference_date = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
    columns = [
        column
        for column in (
            'DT_NOTIFIC', 'ID_MUNICIP', 'NDUPLIC_N', 'CLASSI_FIN',
            'EVOLUCAO', 'HOSPITALIZ',
        )
        if column in available
    ]
    aggregates = {}
    discarded_dates = 0
    discarded_municipalities = 0
    excluded_duplicates = 0
    valid_rows = 0

    parquet = pq.ParquetFile(input_path)
    try:
        for batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
            df = batch.to_pandas()
            df['DT_NOTIFIC'] = pd.to_datetime(df['DT_NOTIFIC'], errors='coerce')
            df['ID_MUNICIP'] = pd.to_numeric(
                df['ID_MUNICIP'], errors='coerce'
            ).astype('Int64')
            valid_date = df['DT_NOTIFIC'].notna() & df['DT_NOTIFIC'].le(reference_date)
            valid_municipality = df['ID_MUNICIP'].notna()
            discarded_dates += int((~valid_date).sum())
            discarded_municipalities += int(
                (valid_date & ~valid_municipality).sum()
            )
            df = df.loc[valid_date & valid_municipality].copy()
            if 'NDUPLIC_N' in df:
                duplicate_mask = pd.to_numeric(
                    df['NDUPLIC_N'], errors='coerce'
                ).eq(2).fillna(False)
                excluded_duplicates += int(duplicate_mask.sum())
                df = df.loc[~duplicate_mask].copy()
            if df.empty:
                continue

            df['MES_REFERENCIA'] = (
                df['DT_NOTIFIC'].dt.to_period('M').dt.to_timestamp()
            )
            classifications = (
                df['CLASSI_FIN'].astype('string').str.lower()
                if 'CLASSI_FIN' in df
                else pd.Series('', index=df.index, dtype='string')
            )
            df['CASO_DENGUE'] = classifications.isin(
                DENGUE_CLASSIFICATIONS
            ).astype('int64')
            evolution = (
                df['EVOLUCAO'].astype('string').str.lower()
                if 'EVOLUCAO' in df
                else pd.Series('', index=df.index, dtype='string')
            )
            df['OBITO_DENGUE'] = (
                evolution.eq('obito_dengue').fillna(False).astype('int64')
            )
            hospitalized = (
                pd.to_numeric(df['HOSPITALIZ'], errors='coerce').eq(1)
                if 'HOSPITALIZ' in df
                else pd.Series(False, index=df.index)
            )
            df['HOSPITALIZACAO'] = hospitalized.fillna(False).astype('int64')
            monthly = (
                df.groupby(['MES_REFERENCIA', 'ID_MUNICIP'], observed=True)
                .agg(
                    NOTIFICACOES=('ID_MUNICIP', 'size'),
                    CASOS_DENGUE=('CASO_DENGUE', 'sum'),
                    OBITOS_DENGUE=('OBITO_DENGUE', 'sum'),
                    HOSPITALIZACOES=('HOSPITALIZACAO', 'sum'),
                )
            )
            valid_rows += len(df)
            for (month, municipality), row in monthly.iterrows():
                key = (pd.Timestamp(month), int(municipality))
                values = tuple(
                    int(row[column])
                    for column in (
                        'NOTIFICACOES', 'CASOS_DENGUE',
                        'OBITOS_DENGUE', 'HOSPITALIZACOES',
                    )
                )
                current = aggregates.get(key, (0, 0, 0, 0))
                aggregates[key] = tuple(
                    previous + value
                    for previous, value in zip(current, values)
                )
    finally:
        parquet.close()

    print(
        f'Ouro: {discarded_dates:,} registros com data inválida/futura e '
        f'{discarded_municipalities:,} sem município excluídos.'
    )
    print(
        f'Ouro: {excluded_duplicates:,} registros marcados NDUPLIC_N=2 '
        'excluídos das métricas.'
    )
    if not valid_rows:
        raise ValueError('A camada Prata não contém linhas válidas para a Ouro.')

    municipios = pd.read_csv(municipalities_path or RAW / 'municipios.csv')
    municipios['codigo_ibge'] = pd.to_numeric(
        municipios['codigo_ibge'], errors='raise'
    ).astype('int64')
    municipios['ID_MUNICIP'] = (municipios['codigo_ibge'] // 10).astype('int64')
    if municipios['ID_MUNICIP'].duplicated().any():
        raise ValueError('A dimensão municipios.csv possui IDs municipais repetidos.')
    municipios = municipios.set_index('ID_MUNICIP')

    gold_rows = [
        (month, municipality, *values)
        for (month, municipality), values in aggregates.items()
    ]
    df_ouro = pd.DataFrame(
        gold_rows,
        columns=[
            'MES_REFERENCIA', 'ID_MUNICIP', 'NOTIFICACOES',
            'CASOS_DENGUE', 'OBITOS_DENGUE', 'HOSPITALIZACOES',
        ],
    )
    df_ouro = df_ouro.sort_values(
        ['MES_REFERENCIA', 'ID_MUNICIP']
    ).reset_index(drop=True)
    df_ouro['MUNICIPIO'] = df_ouro['ID_MUNICIP'].map(municipios['nome'])
    df_ouro['UF'] = (
        pd.to_numeric(
            df_ouro['ID_MUNICIP'].map(municipios['codigo_uf']),
            errors='coerce',
        )
        .astype('Int64')
        .astype('string')
        .str.zfill(2)
    )
    missing_municipalities = df_ouro['MUNICIPIO'].isna() | df_ouro['UF'].isna()
    if missing_municipalities.any():
        missing_ids = (
            df_ouro.loc[missing_municipalities, 'ID_MUNICIP']
            .drop_duplicates()
            .head(10)
            .tolist()
        )
        raise ValueError(
            'Não foi possível associar todos os municípios à dimensão '
            f'municipios.csv. IDs de exemplo: {missing_ids}'
        )
    df_ouro = df_ouro[
        [
            'MES_REFERENCIA', 'ID_MUNICIP', 'UF', 'MUNICIPIO',
            'NOTIFICACOES', 'CASOS_DENGUE', 'OBITOS_DENGUE',
            'HOSPITALIZACOES',
        ]
    ]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f'.{output_path.name}.{uuid.uuid4().hex}.tmp'
    )
    try:
        df_ouro.to_parquet(temporary_path, index=False)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return df_ouro


if __name__ == '__main__':
    result = gold_acumulado_municipio()
    print(f'Camada Ouro gerada: {len(result):,} registros em {PROCESSED / "df_ouro.parquet"}')
