from config import DADOS
import pandas as pd
import numpy as np
def etl():
    df_25 = pd.read_parquet(f'{DADOS} / df_bronze_25.parquet ')
    df_26 = pd.read_parquet(f'{DADOS} / df_bronze_26.parquet ')

    df = pd.concat([df_25 , df_26])

    # ============================================================
    # 4. CONVERSÃO DE COLUNAS DE DATA
    # ============================================================
    DATE_COLS = [
        'DT_NOTIFIC', 'DT_SIN_PRI', 'DT_INVEST', 'DT_SORO', 'DT_NS1',
        'DT_PCR', 'DT_INTERNA', 'DT_ENCERRA', 'DT_ALRM', 'DT_GRAV',
        'DT_DIGITA', 'DT_OBITO'
    ]
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # DT_VIRAL
    if 'DT_VIRAL' in df.columns:
        df['DT_VIRAL'] = pd.to_datetime(df['DT_VIRAL'], errors='coerce')

    # Colunas de chikungunya (quase sempre vazias)
    for col in ['DT_CHIK_S1', 'DT_CHIK_S2', 'DT_PRNT']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    
    date_cols = [c for c in df.columns if 'DT_' in c and pd.api.types.is_datetime64_any_dtype(df[c])]
    

    

    # ============================================================
    # 5.1 Colunas binárias (1=Sim, 2=Não) - converter com tolerância
    # ============================================================
    def safe_to_int64(ser):
        return pd.to_numeric(ser, errors="coerce").astype("Int64")

    BINARY_COLS = [
    'FEBRE', 'MIALGIA', 'CEFALEIA', 'EXANTEMA', 'VOMITO', 'NAUSEA',
    'DOR_COSTAS', 'CONJUNTVIT', 'ARTRITE', 'ARTRALGIA', 'PETEQUIA_N',
    'LEUCOPENIA', 'LACO', 'DOR_RETRO', 'DIABETES', 'HEMATOLOG',
    'HEPATOPAT', 'RENAL', 'HIPERTENSA', 'ACIDO_PEPT', 'AUTO_IMUNE',
    'HOSPITALIZ', 'ALRM_HIPOT', 'ALRM_PLAQ', 'ALRM_VOM', 'ALRM_SANG',
    'ALRM_HEMAT', 'ALRM_ABDOM', 'ALRM_LETAR', 'ALRM_HEPAT', 'ALRM_LIQ',
    'GRAV_PULSO', 'GRAV_CONV', 'GRAV_ENCH', 'GRAV_INSUF', 'GRAV_TAQUI',
    'GRAV_EXTRE', 'GRAV_HIPOT', 'GRAV_HEMAT', 'GRAV_MELEN', 'GRAV_METRO',
    'GRAV_SANG', 'GRAV_AST', 'GRAV_MIOC', 'GRAV_CONSC', 'GRAV_ORGAO',
    'MANI_HEMOR', 'EPISTAXE', 'GENGIVO', 'METRO', 'PETEQUIAS',
    'HEMATURA', 'SANGRAM', 'LACO_N', 'PLASMATICO', 'EVIDENCIA',
    'PLAQ_MENOR', 'CON_FHD', 'TPAUTOCTO', 'CLINC_CHIK'
    ]
    for col in BINARY_COLS:
        if col in df.columns:
            df[col] = safe_to_int64(df[col])

    # ============================================================
    # 5.2 Resultados de exames e outras colunas numéricas
    # ============================================================
    NUM_COLS = [
    'RESUL_SORO', 'RESUL_NS1', 'RESUL_VI_N', 'RESUL_PCR_',
    'RES_CHIKS1', 'RES_CHIKS2', 'RESUL_PRNT', 'SOROTIPO',
    'HISTOPA_N', 'IMUNOH_N', 'COMPLICA', 'DOENCA_TRA',
    'TP_NOT', 'CS_FLXRET', 'FLXRECEBI', 'MIGRADO_W',
    'NDUPLIC_N', 'TP_SISTEMA'
    ]
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = safe_to_int64(df[col])

    ID_COLS = [
    'ID_MUNICIP', 'ID_REGIONA', 'ID_UNIDADE', 'ID_MN_RESI',
    'ID_RG_RESI', 'ID_PAIS', 'ID_OCUPA_N', 'MUNICIPIO',
    'COUFINF', 'COPAISINF', 'COMUNINF'
    ]
    for col in ID_COLS:
        if col in df.columns:
            df[col] = safe_to_int64(df[col])

    UF_MAP = {
    'ac': '12', 'al': '27', 'ap': '16', 'am': '13', 'ba': '29', 'ce': '23',
    'df': '53', 'es': '32', 'go': '52', 'ma': '21', 'mt': '51', 'ms': '50',
    'mg': '31', 'pa': '15', 'pb': '25', 'pr': '41', 'pe': '26', 'pi': '22',
    'rj': '33', 'rn': '24', 'rs': '43', 'ro': '11', 'rr': '14', 'sc': '42',
    'sp': '35', 'se': '28', 'to': '17'
    }

    def padronizar_uf(ser):
        s = ser.astype(str).str.lower().str.strip()
        s = s.map(lambda x: UF_MAP.get(x, x)) 
        s = s.replace(['nan', 'none', ''], None)
        s = s.str.zfill(2) 
        return s.astype('category')

    for col in ['SG_UF_NOT', 'SG_UF', 'UF']:
        if col in df.columns:
            df[col] = padronizar_uf(df[col])

    # ============================================================
    # 6.1 Sexo
    # ============================================================
    df['CS_SEXO'] = df['CS_SEXO'].astype(str).str.upper().str.strip()
    df['CS_SEXO'] = df['CS_SEXO'].replace(['I', 'NAN', 'NONE', ''], None)
    df['CS_SEXO'] = df['CS_SEXO'].astype('category')
    

    GESTANT_MAP = {
    1: '1o_trimestre', 2: '2o_trimestre', 3: '3o_trimestre',
    4: 'id_gest_ignorada', 5: 'nao', 6: 'nao_se_aplica', 9: 'ignorado'
    }
    df['CS_GESTANT'] = safe_to_int64(df['CS_GESTANT']).map(GESTANT_MAP).astype('category')

    RACA_MAP = {1: 'Branca', 2: 'Preta', 3: 'Amarela', 4: 'Parda', 5: 'Indígena'}
    df['CS_RACA'] = safe_to_int64(df['CS_RACA']).map(RACA_MAP).astype('category')


    ESCOL_MAP = {
    0: 'sem_escolaridade', 1: 'fund_incompleto_1a4', 2: 'fund_completo_5a8',
    3: 'fund_completo', 4: 'medio_incompleto', 5: 'medio_completo',
    6: 'superior_incompleto', 7: 'superior_completo', 8: 'nao_se_aplica',
    9: 'ignorado', 10: 'fund_1a4'
}
    df['CS_ESCOL_N'] = safe_to_int64(df['CS_ESCOL_N']).map(ESCOL_MAP).astype('category')

    CLASSI_MAP = {
    0: 'descartado', 1: 'dengue_classico', 2: 'dengue_hemorragico',
    3: 'sindrome_choque', 4: 'sindrome_especial', 5: 'obito_dengue',
    8: 'inconclusivo', 10: 'dengue', 11: 'chikungunya',
    12: 'doenca_aguda_nao_especificada', 13: 'zika'
}
    df['CLASSI_FIN'] = safe_to_int64(df['CLASSI_FIN']).map(CLASSI_MAP).astype('category')

    CRITERIO_MAP = {
    0: 'descartado', 1: 'laboratorial', 2: 'clinico_epidemiologico',
    3: 'vinculo_epidemiologico', 4: 'exame_inespecifico'
}
    df['CRITERIO'] = safe_to_int64(df['CRITERIO']).map(CRITERIO_MAP).astype('category')

    EVOLUCAO_MAP = {0: 'ignorado', 1: 'cura', 2: 'obito_dengue', 3: 'obito_outra_causa'}
    df['EVOLUCAO'] = safe_to_int64(df['EVOLUCAO']).map(EVOLUCAO_MAP).astype('category')
    df['ID_AGRAVO'] = df['ID_AGRAVO'].astype('category')

    df['NU_IDADE_N'] = safe_to_int64(df['NU_IDADE_N'])
    df['ANO_NASC'] = safe_to_int64(df['ANO_NASC'])

    def decode_idade(val):
        if pd.isna(val):
            return ('ignorado', 0)
        v = int(val)
        if v >= 4000:  return ('anos', v - 4000)
        elif v >= 3000: return ('meses', v - 3000)
        elif v >= 2000: return ('dias', v - 2000)
        elif v >= 1000: return ('horas', v - 1000)
        return ('ignorado', 0)

    df['IDADE_TIPO'] = df['NU_IDADE_N'].apply(lambda x: decode_idade(x)[0])
    df['IDADE_VALOR'] = df['NU_IDADE_N'].apply(lambda x: decode_idade(x)[1])
    df['IDADE_ANOS'] = np.where(
        df['IDADE_TIPO'] == 'anos', df['IDADE_VALOR'],
        np.where(df['IDADE_TIPO'] == 'meses', (df['IDADE_VALOR'] / 12).round(1),
                np.where(df['IDADE_TIPO'] == 'dias', (df['IDADE_VALOR'] / 365).round(3), None))
    )

    FILL_COLS = (
    ['FEBRE', 'MIALGIA', 'CEFALEIA', 'EXANTEMA', 'VOMITO', 'NAUSEA',
     'DOR_COSTAS', 'CONJUNTVIT', 'ARTRITE', 'ARTRALGIA', 'PETEQUIA_N',
     'LEUCOPENIA', 'LACO', 'DOR_RETRO', 'DIABETES', 'HEMATOLOG',
     'HEPATOPAT', 'RENAL', 'HIPERTENSA', 'ACIDO_PEPT', 'AUTO_IMUNE']
    + [c for c in df.columns if c.startswith('ALRM_')]
    + [c for c in df.columns if c.startswith('GRAV_')]
    + ['MANI_HEMOR', 'EPISTAXE', 'GENGIVO', 'METRO', 'PETEQUIAS',
       'HEMATURA', 'SANGRAM', 'LACO_N', 'PLASMATICO', 'EVIDENCIA',
       'PLAQ_MENOR', 'CON_FHD', 'CLINC_CHIK', 'HOSPITALIZ',
       'TPAUTOCTO']
    )
    for col in FILL_COLS:
        if col in df.columns and df[col].isna().any():
            df[col] = df[col].fillna(2)
            
    df.to_parquet(f'{DADOS} / df_prata.parquet')
    return df

