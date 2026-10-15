from con_db import con_sql
from config import DADOS
import pandas as pd

def read_data():
    conn, status = con_sql()
    if conn:
        df_bronze_25 = pd.read_sql('select * from DENGBR25 ', conn)
        df_bronze_26 = pd.read_sql('select * from DENGBR26 ', conn)
        conn.close()

        df_bronze_25.to_parquet(f'{DADOS}/df_bronze_25.parquet')
        df_bronze_26.to_parquet(f'{DADOS}/df_bronze_26.parquet')
        print(df_bronze_25.shape)
        return df_bronze_25 , df_bronze_26

read_data()