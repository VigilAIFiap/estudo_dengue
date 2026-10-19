from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROCESSED, RAW


DATE_COLUMNS = (
    'DT_NOTIFIC', 'DT_SIN_PRI', 'DT_INVEST', 'DT_SORO', 'DT_NS1',
    'DT_VIRAL', 'DT_PCR', 'DT_INTERNA', 'DT_ENCERRA', 'DT_ALRM',
    'DT_GRAV', 'DT_DIGITA', 'DT_OBITO', 'DT_CHIK_S1', 'DT_CHIK_S2',
    'DT_PRNT',
)
NUMERIC_COLUMNS = (
    'FEBRE', 'MIALGIA', 'CEFALEIA', 'EXANTEMA', 'VOMITO', 'NAUSEA',
    'DOR_COSTAS', 'CONJUNTVIT', 'ARTRITE', 'ARTRALGIA', 'PETEQUIA_N',
    'LEUCOPENIA', 'DOR_RETRO', 'DIABETES', 'HEMATOLOG', 'HEPATOPAT',
    'RENAL', 'HIPERTENSA', 'ACIDO_PEPT', 'AUTO_IMUNE', 'HOSPITALIZ',
    'NDUPLIC_N', 'NU_IDADE_N', 'ANO_NASC', 'SEM_NOT', 'SEM_PRI',
    'NU_ANO', 'ID_MUNICIP', 'ID_MN_RESI', 'ID_RG_RESI', 'ID_PAIS',
)
DROP_COLUMNS = {
    'INDEX', 'TP_NOT', 'ID_AGRAVO', 'ID_REGIONA', 'ID_UNIDADE',
    'ID_OCUPA_N', 'LACO', 'RES_CHIKS1', 'RES_CHIKS2', 'RESUL_PRNT',
    'RESUL_SORO', 'RESUL_NS1', 'RESUL_VI_N', 'RESUL_PCR_', 'SOROTIPO',
    'HISTOPA_N', 'IMUNOH_N', 'TPAUTOCTO', 'COUFINF', 'COPAISINF',
    'COMUNINF', 'CRITERIO', 'DOENCA_TRA', 'CLINC_CHIK', 'ALRM_HIPOT',
    'ALRM_PLAQ', 'ALRM_VOM', 'ALRM_SANG', 'ALRM_HEMAT', 'ALRM_ABDOM',
    'ALRM_LETAR', 'ALRM_HEPAT', 'ALRM_LIQ', 'GRAV_PULSO', 'GRAV_CONV',
    'GRAV_ENCH', 'GRAV_INSUF', 'GRAV_TAQUI', 'GRAV_EXTRE', 'GRAV_HIPOT',
    'GRAV_HEMAT', 'GRAV_MELEN', 'GRAV_METRO', 'GRAV_SANG', 'GRAV_AST',
    'GRAV_MIOC', 'GRAV_CONSC', 'GRAV_ORGAO', 'MANI_HEMOR', 'EPISTAXE',
    'GENGIVO', 'METRO', 'PETEQUIAS', 'HEMATURA', 'SANGRAM', 'LACO_N',
    'PLASMATICO', 'EVIDENCIA', 'PLAQ_MENOR', 'CON_FHD', 'COMPLICA',
    'TP_SISTEMA', 'CS_FLXRET', 'FLXRECEBI', 'MIGRADO_W', 'SIAFI_ID',
    'DDD', 'FUSO_HORARIO', 'IDADE_TIPO', 'IDADE_VALOR',
}
UF_CODES = {
    'RO': '11', 'AC': '12', 'AM': '13', 'RR': '14', 'PA': '15',
    'AP': '16', 'TO': '17', 'MA': '21', 'PI': '22', 'CE': '23',
    'RN': '24', 'PB': '25', 'PE': '26', 'AL': '27', 'SE': '28',
    'BA': '29', 'MG': '31', 'ES': '32', 'RJ': '33', 'SP': '35',
    'PR': '41', 'SC': '42', 'RS': '43', 'MS': '50', 'MT': '51',
    'GO': '52', 'DF': '53',
}
GESTANT_MAP = {
    1: '1o_trimestre', 2: '2o_trimestre', 3: '3o_trimestre',
    4: 'id_gest_ignorada', 5: 'nao', 6: 'nao_se_aplica', 9: 'ignorado',
}
RACA_MAP = {
    1: 'Branca', 2: 'Preta', 3: 'Amarela', 4: 'Parda',
    5: 'Indígena', 9: 'Ignorado',
}
ESCOL_MAP = {
    0: 'analfabeto',
    1: 'fundamental_incompleto_1a4',
    2: 'quarta_serie_completa',
    3: 'fundamental_incompleto_5a8',
    4: 'fundamental_completo',
    5: 'medio_incompleto',
    6: 'medio_completo',
    7: 'superior_incompleto',
    8: 'superior_completo',
    9: 'ignorado',
    10: 'nao_se_aplica',
    99: 'ignorado',
}
# Codes 10–13 follow the current SINAN classification used by the API and
# observed in the 2023–2026 extracts. Older dictionary codes are not guessed.
CLASSI_MAP = {
    0: 'codigo_0_nao_documentado',
    5: 'descartado',
    8: 'inconclusivo',
    9: 'ignorado',
    10: 'dengue',
    11: 'dengue_com_sinais_de_alarme',
    12: 'dengue_grave',
    13: 'chikungunya',
}
EVOLUCAO_MAP = {
    0: 'codigo_0_nao_documentado',
    1: 'cura',
    2: 'obito_dengue',
    3: 'obito_outra_causa',
    4: 'obito_em_investigacao',
    9: 'ignorado',
}


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace(r'^\s*$', pd.NA, regex=True), errors='coerce')


def _map_codes(series: pd.Series, mapping: dict[int, str]) -> pd.Series:
    codes = _numeric(series)
    mapped = codes.map(mapping).astype('string')
    unknown = codes.notna() & mapped.isna()
    mapped.loc[unknown] = (
        'codigo_' + codes.loc[unknown].astype('Int64').astype('string')
        + '_nao_mapeado'
    )
    return mapped


def _load_bronze(input_dir: Path) -> tuple[pd.DataFrame, ...]:
    paths = [input_dir / f'df_bronze_{year}.parquet' for year in (23, 24, 25, 26)]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            'Parquets Bronze ausentes: ' + ', '.join(missing)
            + '. Execute primeiro: python src\\read_data_bronze.py'
        )
    return tuple(pd.read_parquet(path) for path in paths)


def _municipal_dimension(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f'Dimensão de municípios não encontrada: {path}')
    municipalities = pd.read_csv(path)
    required = {'codigo_ibge', 'nome', 'codigo_uf'}
    missing = required.difference(municipalities.columns)
    if missing:
        raise ValueError(
            f'Colunas ausentes em municipios.csv: {sorted(missing)}'
        )

    municipalities['codigo_ibge'] = pd.to_numeric(
        municipalities['codigo_ibge'], errors='raise'
    ).astype('int64')
    municipalities['ID_MUNICIP'] = municipalities['codigo_ibge'] // 10
    if municipalities['ID_MUNICIP'].duplicated().any():
        raise ValueError('municipios.csv possui IDs municipais repetidos.')
    municipalities = municipalities.rename(
        columns={
            'latitude': 'LATITUDE',
            'longitude': 'LONGITUDE',
            'capital': 'CAPITAL',
            'codigo_uf': 'CODIGO_UF',
            'codigo_ibge': 'CODIGO_IBGE',
            'nome': 'NOME',
        }
    )
    return municipalities[
        [
            'ID_MUNICIP', 'CODIGO_IBGE', 'NOME', 'LATITUDE',
            'LONGITUDE', 'CAPITAL', 'CODIGO_UF',
        ]
    ]


def _report_quality(df: pd.DataFrame) -> None:
    exact_duplicates = int(df.duplicated().sum())
    print(f'Revisão Prata: {len(df):,} linhas; {exact_duplicates:,} duplicatas exatas.')
    null_counts = df.isna().sum()
    null_counts = null_counts[null_counts.gt(0)].sort_values(ascending=False)
    if null_counts.empty:
        print('  Nulos: nenhum.')
    else:
        print('  Nulos por coluna (quantidade/percentual):')
        for column, count in null_counts.items():
            print(f'    {column}: {int(count):,} ({count / len(df):.1%})')
    if 'NDUPLIC_N' in df:
        counts = _numeric(df['NDUPLIC_N']).value_counts(dropna=False).sort_index()
        print(f'  NDUPLIC_N (códigos brutos): {counts.to_dict()}')

    date_rules = (
        ('DT_SIN_PRI', 'DT_NOTIFIC', 'início dos sintomas posterior à notificação'),
        ('DT_INVEST', 'DT_NOTIFIC', 'investigação anterior à notificação'),
    )
    for earlier_col, later_col, description in date_rules:
        if earlier_col not in df or later_col not in df:
            continue
        earlier = pd.to_datetime(df[earlier_col], errors='coerce')
        later = pd.to_datetime(df[later_col], errors='coerce')
        invalid = earlier.notna() & later.notna() & (
            earlier.gt(later) if earlier_col == 'DT_SIN_PRI' else earlier.lt(later)
        )
        print(f'  ATENÇÃO: {int(invalid.sum()):,} registros com {description}; preservados.')

    exam_dates = (
        'DT_SORO', 'DT_NS1', 'DT_PCR', 'DT_VIRAL',
        'DT_CHIK_S1', 'DT_CHIK_S2', 'DT_PRNT',
    )
    if 'DT_SIN_PRI' in df:
        symptoms = pd.to_datetime(df['DT_SIN_PRI'], errors='coerce')
        for column in exam_dates:
            if column not in df:
                continue
            exam = pd.to_datetime(df[column], errors='coerce')
            invalid = exam.notna() & symptoms.notna() & exam.lt(symptoms)
            print(
                f'  ATENÇÃO: {int(invalid.sum()):,} exames {column} anteriores '
                'ao início dos sintomas; preservados.'
            )

    today = pd.Timestamp.today().normalize()
    for column in DATE_COLUMNS:
        if column not in df:
            continue
        dates = pd.to_datetime(df[column], errors='coerce')
        old = int((dates < pd.Timestamp('1900-01-01')).sum())
        future = int((dates > today).sum())
        if old or future:
            print(
                f'  ATENÇÃO {column}: {old:,} datas anteriores a 1900; '
                f'{future:,} datas futuras; preservadas.'
            )


def etl(
    bronze_data: tuple[pd.DataFrame, ...] | None = None,
    input_dir: Path | None = None,
    municipalities_path: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Transform cached or supplied SINAN Bronze frames into the Silver layer."""
    frames = bronze_data if bronze_data is not None else _load_bronze(input_dir or PROCESSED)
    if len(frames) != 4:
        raise ValueError('São esperados quatro DataFrames Bronze (2023–2026).')
    if any(not isinstance(frame, pd.DataFrame) for frame in frames):
        raise TypeError('Cada entrada Bronze deve ser um DataFrame pandas.')
    for year, frame in zip((23, 24, 25, 26), frames):
        print(f'Bronze DENGBR{year}: {len(frame):,} linhas.')

    df = pd.concat(frames, ignore_index=True, sort=False)
    df.columns = [str(column).strip().upper() for column in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError('Há nomes de colunas repetidos após normalização.')
    for column in df.select_dtypes(include=['object', 'string']).columns:
        df[column] = df[column].replace(r'^\s*$', pd.NA, regex=True)
    required = {'DT_NOTIFIC', 'ID_MUNICIP'}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f'Colunas obrigatórias ausentes na Bronze: {sorted(missing)}')

    for column in DATE_COLUMNS:
        if column in df:
            df[column] = pd.to_datetime(df[column], errors='coerce')
    for column in NUMERIC_COLUMNS:
        if column in df:
            df[column] = _numeric(df[column]).astype('Int64')

    if 'CS_SEXO' in df:
        sex = df['CS_SEXO'].astype('string').str.strip().str.upper()
        df['CS_SEXO'] = sex.replace({'': pd.NA, 'NAN': pd.NA, 'NONE': pd.NA})
    for column, mapping in (
        ('CS_GESTANT', GESTANT_MAP),
        ('CS_RACA', RACA_MAP),
        ('CS_ESCOL_N', ESCOL_MAP),
        ('CLASSI_FIN', CLASSI_MAP),
        ('EVOLUCAO', EVOLUCAO_MAP),
    ):
        if column in df:
            df[column] = _map_codes(df[column], mapping)

    if 'NU_IDADE_N' in df:
        age_code = df['NU_IDADE_N']
        age_type = pd.Series('ignorado', index=df.index, dtype='string')
        age_value = pd.Series(pd.NA, index=df.index, dtype='Float64')
        ranges = (
            (age_code.ge(1000) & age_code.lt(2000), 'horas', 1000),
            (age_code.ge(2000) & age_code.lt(3000), 'dias', 2000),
            (age_code.ge(3000) & age_code.lt(4000), 'meses', 3000),
            (age_code.ge(4000), 'anos', 4000),
        )
        for mask, label, offset in ranges:
            age_type.loc[mask] = label
            age_value.loc[mask] = age_code.loc[mask] - offset
        df['IDADE_TIPO'] = age_type
        df['IDADE_VALOR'] = age_value
        years = pd.Series(np.nan, index=df.index, dtype='float64')
        years.loc[age_type.eq('anos')] = age_value.loc[age_type.eq('anos')]
        years.loc[age_type.eq('meses')] = (
            age_value.loc[age_type.eq('meses')] / 12
        ).round(1)
        years.loc[age_type.eq('dias')] = (
            age_value.loc[age_type.eq('dias')] / 365
        ).round(3)
        df['IDADE_ANOS'] = years

    municipality_path = municipalities_path or RAW / 'municipios.csv'
    municipalities = _municipal_dimension(municipality_path)
    df['ID_MUNICIP'] = _numeric(df['ID_MUNICIP']).astype('Int64')
    df = df.merge(
        municipalities,
        on='ID_MUNICIP',
        how='left',
        validate='many_to_one',
    )
    unmatched = df['ID_MUNICIP'].notna() & df['CODIGO_IBGE'].isna()
    if unmatched.any():
        sample = df.loc[unmatched, 'ID_MUNICIP'].drop_duplicates().head(10).tolist()
        raise ValueError(
            f'{int(unmatched.sum()):,} notificações sem correspondência em '
            f'municipios.csv. IDs de exemplo: {sample}'
        )

    df['MUNICIPIO'] = df['NOME'].astype('string')
    uf = _numeric(df['CODIGO_UF']).astype('Int64').astype('string').str.zfill(2)
    df['UF'] = uf
    if 'SG_UF_NOT' in df:
        source_uf = df['SG_UF_NOT'].astype('string').str.strip().str.upper()
        source_uf = source_uf.replace(UF_CODES)
        source_uf = source_uf.str.replace(r'\.0$', '', regex=True)
        source_uf = source_uf.where(source_uf.str.fullmatch(r'\d{1,2}')).str.zfill(2)
        df['SG_UF_NOT'] = source_uf
    if 'SG_UF' in df:
        source_uf = df['SG_UF'].astype('string').str.strip().str.upper()
        source_uf = source_uf.replace(UF_CODES)
        source_uf = source_uf.str.replace(r'\.0$', '', regex=True)
        df['SG_UF'] = source_uf.where(
            source_uf.str.fullmatch(r'\d{1,2}')
        ).str.zfill(2)

    df = df.drop(columns=[column for column in DROP_COLUMNS if column in df])
    _report_quality(df)

    destination = Path(output_path or PROCESSED / 'df_prata.parquet')
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Gera a camada Prata a partir dos Parquets Bronze locais.'
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        default=PROCESSED,
        help='Diretório com df_bronze_23..26.parquet.',
    )
    parser.add_argument(
        '--municipalities',
        type=Path,
        default=RAW / 'municipios.csv',
        help='Caminho para municipios.csv.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=PROCESSED / 'df_prata.parquet',
        help='Caminho para o Parquet Prata gerado.',
    )
    args = parser.parse_args()
    result = etl(
        input_dir=args.input_dir,
        municipalities_path=args.municipalities,
        output_path=args.output,
    )
    print(f'Camada Prata gerada: {len(result):,} registros em {args.output}')


if __name__ == '__main__':
    main()
