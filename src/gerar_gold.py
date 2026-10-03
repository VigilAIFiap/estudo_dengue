from config import DADOS
import pandas as pd

def gold_acumulado_municipio():
    df_gold = pd.read_parquet(f'{DADOS} /  / df_prata.parquet')

    df_gold.to_parquet(f'{DADOS} / df_gold.parquet')
    return df_gold