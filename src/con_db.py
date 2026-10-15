import os
import oracledb
from dotenv import load_dotenv

load_dotenv()

def con_sql():
    
    try:
        conn = oracledb.connect(
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            dsn=os.environ["DB_DSN"],
            config_dir=os.environ["WALLET_DIR"],
            wallet_location=os.environ["WALLET_DIR"],
            wallet_password=os.environ["WALLET_PASSWORD"],
        )
        with conn.cursor() as cur:
            cur.execute("select 1 from dual")   # teste real: confirma que o banco respondeu
            cur.fetchone()
        return conn, "Conectado com sucesso"

    except KeyError as e:
        return None, f"Variável de ambiente ausente: {e}"
    except oracledb.Error as e:
        erro, = e.args
        return None, f"Erro Oracle: {erro.message}"
    except Exception as e:
        return None, f"Erro inesperado: {e}"
