from config import DADOS_TEMPO, DADOS
import pandas as pd
from pathlib import Path

def ler_dados_clima_tempo(pasta=DADOS_TEMPO):
    dfs = []
    for arquivo in Path(pasta).glob("*.csv"):
        try:
            df = pd.read_csv(
                arquivo,
                sep=";",       
                decimal=",",     
                engine="python"
            )
            
            dfs.append(df)
        except Exception as e:
            print(f"Erro ao ler {arquivo}: {e}")

    if not dfs:
        raise ValueError("Nenhum arquivo foi lido. Verifique a pasta e formato.")

    df_final = pd.concat(dfs, ignore_index=True).drop(columns = {'Unnamed: 6', 'arquivo_origem'})
    
    df_final.to_parquet(f"{DADOS}/df_clima_tempo.parquet")  
    return df_final

df = ler_dados_clima_tempo()
