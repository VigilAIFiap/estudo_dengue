from __future__ import annotations

from pathlib import Path

import pandas as pd

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
):
    input_path = input_path or PROCESSED / 'df_prata.parquet'
    output_path = output_path or PROCESSED / 'df_ouro.parquet'
    df = pd.read_parquet(input_path)

    required = {'DT_NOTIFIC', 'ID_MUNICIP'}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f'Colunas obrigatórias ausentes na Prata: {sorted(missing)}')

    df['DT_NOTIFIC'] = pd.to_datetime(df['DT_NOTIFIC'], errors='coerce')
    df['ID_MUNICIP'] = pd.to_numeric(df['ID_MUNICIP'], errors='coerce').astype('Int64')
    reference_date = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
    valid_date = df['DT_NOTIFIC'].notna() & df['DT_NOTIFIC'].le(reference_date)
    valid_municipality = df['ID_MUNICIP'].notna()
    discarded_dates = int((~valid_date).sum())
    discarded_municipalities = int((valid_date & ~valid_municipality).sum())
    df = df.loc[valid_date & valid_municipality].copy()
    print(
        f'Ouro: {discarded_dates:,} registros com data inválida/futura e '
        f'{discarded_municipalities:,} sem município excluídos.'
    )
    if 'NDUPLIC_N' in df:
        duplicates_to_exclude = (
            pd.to_numeric(df['NDUPLIC_N'], errors='coerce').eq(2).fillna(False)
        )
        excluded = int(duplicates_to_exclude.sum())
        df = df.loc[~duplicates_to_exclude].copy()
        print(f'Ouro: {excluded:,} registros marcados NDUPLIC_N=2 excluídos das métricas.')
    df['MES_REFERENCIA'] = df['DT_NOTIFIC'].dt.to_period('M').dt.to_timestamp()

    municipios = pd.read_csv(municipalities_path or RAW / 'municipios.csv')
    municipios['codigo_ibge'] = pd.to_numeric(
        municipios['codigo_ibge'], errors='raise'
    ).astype('int64')
    municipios['ID_MUNICIP'] = (municipios['codigo_ibge'] // 10).astype('int64')
    if municipios['ID_MUNICIP'].duplicated().any():
        raise ValueError('A dimensão municipios.csv possui IDs municipais repetidos.')
    municipios = municipios.set_index('ID_MUNICIP')

    classifications = (
        df['CLASSI_FIN'].astype('string').str.lower()
        if 'CLASSI_FIN' in df.columns
        else pd.Series('', index=df.index, dtype='string')
    )
    df['CASO_DENGUE'] = classifications.isin(DENGUE_CLASSIFICATIONS).astype('int64')

    evolution = (
        df['EVOLUCAO'].astype('string').str.lower()
        if 'EVOLUCAO' in df.columns
        else pd.Series('', index=df.index, dtype='string')
    )
    df['OBITO_DENGUE'] = (
        evolution.eq('obito_dengue').fillna(False).astype('int64')
    )

    hospitalized = (
        pd.to_numeric(df['HOSPITALIZ'], errors='coerce').eq(1)
        if 'HOSPITALIZ' in df.columns
        else pd.Series(False, index=df.index)
    )
    df['HOSPITALIZACAO'] = hospitalized.fillna(False).astype('int64')

    keys = ['MES_REFERENCIA', 'ID_MUNICIP']
    df_ouro = (
        df.groupby(keys, dropna=False, observed=True)
        .agg(
            NOTIFICACOES=('ID_MUNICIP', 'size'),
            CASOS_DENGUE=('CASO_DENGUE', 'sum'),
            OBITOS_DENGUE=('OBITO_DENGUE', 'sum'),
            HOSPITALIZACOES=('HOSPITALIZACAO', 'sum'),
        )
        .reset_index()
        .sort_values(keys, na_position='last')
        .reset_index(drop=True)
    )
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
    df_ouro.to_parquet(output_path, index=False)
    return df_ouro


if __name__ == '__main__':
    result = gold_acumulado_municipio()
    print(f'Camada Ouro gerada: {len(result):,} registros em {PROCESSED / "df_ouro.parquet"}')
