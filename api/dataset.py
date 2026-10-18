"""Carga única e normalização das notificações SINAN para a API.

Regras de leitura da base:
- DENGBR25.csv: somente NU_ANO 2024 e 2025;
- DENGBR26.csv: todas as linhas;
- descarta DT_NOTIFIC inválida ou futura.

A UF é derivada do código IBGE do município notificador (dimensão
municipios.csv), não de SG_UF_NOT, que mistura códigos e siglas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

COLUNAS = [
    "DT_NOTIFIC", "NU_ANO", "SG_UF_NOT", "ID_MUNICIP",
    "HOSPITALIZ", "CLASSI_FIN", "EVOLUCAO",
]

UF_SIGLA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}
UF_NOME = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima",
    "PA": "Pará", "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão",
    "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte", "PB": "Paraíba",
    "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe", "BA": "Bahia",
    "MG": "Minas Gerais", "ES": "Espírito Santo", "RJ": "Rio de Janeiro",
    "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal",
}

# Ficha de notificação SINAN Dengue/Chikungunya (campo Classificação final).
# 8 e 0 não constam na ficha; 8 é usado no SINAN como "Inconclusivo" e 0 não
# tem definição documentada — ambos são exibidos com essa ressalva.
CLASSIFICACAO = {
    10: "Dengue",
    11: "Dengue com sinais de alarme",
    12: "Dengue grave",
    13: "Chikungunya",
    5: "Descartado",
    8: "Inconclusivo",
    0: "Código 0 (não documentado na ficha)",
    -1: "Sem classificação final",
}
CONFIRMADOS = (10, 11, 12)

# Campo Evolução do caso.
EVOLUCAO = {
    1: "Cura",
    2: "Óbito pelo agravo",
    3: "Óbito por outras causas",
    4: "Óbito em investigação",
    9: "Ignorado",
    0: "Código 0 (não documentado na ficha)",
    -1: "Não preenchido",
}
HOSPITALIZACAO = {1: "Sim", 2: "Não", 9: "Ignorado", 0: "Código 0", -1: "Não preenchido"}


@dataclass(frozen=True, eq=False)  # hash por identidade: permite cache por instância
class Dataset:
    notificacoes: pd.DataFrame
    municipios: pd.DataFrame
    carregado_em: datetime
    arquivos: tuple[tuple[str, int, float], ...]  # (nome, bytes, mtime)
    linhas_descartadas: dict[str, int]
    colunas_disponiveis: tuple[str, ...]


def semana_epidemiologica(datas: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Ano, semana e início (domingo) da semana epidemiológica.

    A semana 1 é a semana (domingo a sábado) que contém 4 de janeiro.
    """
    datas = pd.to_datetime(datas).dt.normalize()
    inicio_semana = datas - pd.to_timedelta((datas.dt.weekday + 1) % 7, unit="D")
    # A semana pertence ao ano que contém a maior parte dos seus dias,
    # ou seja, o ano civil da quarta-feira.
    quarta = inicio_semana + pd.Timedelta(days=3)
    ano = quarta.dt.year
    jan4 = pd.to_datetime(ano.astype(str) + "-01-04")
    inicio_s1 = jan4 - pd.to_timedelta((jan4.dt.weekday + 1) % 7, unit="D")
    semana = ((inicio_semana - inicio_s1).dt.days // 7 + 1).astype("int16")
    return ano.astype("int16"), semana, inicio_semana


def _codigo(serie: pd.Series) -> np.ndarray:
    return serie.fillna(-1).astype("int8").to_numpy()


def _cabecalho(arquivo: Path) -> list[str]:
    return pd.read_csv(arquivo, encoding="latin-1", nrows=0).columns.tolist()


def carregar(data_dir: Path, hoje: pd.Timestamp | None = None) -> Dataset:
    hoje = (hoje or pd.Timestamp.today()).normalize()
    arquivo_25 = data_dir / "DENGBR25.csv"
    arquivo_26 = data_dir / "DENGBR26.csv"
    arquivo_mun = data_dir / "municipios.csv"
    for arquivo in (arquivo_25, arquivo_26, arquivo_mun):
        if not arquivo.exists():
            raise FileNotFoundError(f"Arquivo de dados ausente: {arquivo}")

    leitura = dict(
        sep=",",
        encoding="latin-1",
        usecols=COLUNAS,
        dtype={
            "DT_NOTIFIC": str, "NU_ANO": str, "SG_UF_NOT": str,
            "ID_MUNICIP": "float64", "HOSPITALIZ": "float32",
            "CLASSI_FIN": "float32", "EVOLUCAO": "float32",
        },
    )
    bruto_25 = pd.read_csv(arquivo_25, **leitura)
    bruto_26 = pd.read_csv(arquivo_26, **leitura)
    colunas_disponiveis = tuple(
        sorted(set(_cabecalho(arquivo_25)) | set(_cabecalho(arquivo_26)))
    )

    fora_do_ano = int((~bruto_25["NU_ANO"].isin(["2024", "2025"])).sum())
    bruto = pd.concat(
        [bruto_25.loc[bruto_25["NU_ANO"].isin(["2024", "2025"]), COLUNAS], bruto_26[COLUNAS]],
        ignore_index=True,
    )
    datas = pd.to_datetime(bruto["DT_NOTIFIC"], format="%Y-%m-%d", errors="coerce")
    invalidas = int(datas.isna().sum())
    futuras = int((datas > hoje).sum())
    validas = datas.notna() & (datas <= hoje)
    bruto, datas = bruto.loc[validas], datas.loc[validas]

    municipios = pd.read_csv(arquivo_mun)
    municipios["id_municip"] = (municipios["codigo_ibge"].astype("int64") // 10).astype("int32")
    if municipios["id_municip"].duplicated().any():
        raise ValueError("municipios.csv possui códigos municipais repetidos.")
    municipios["uf"] = municipios["codigo_uf"].map(UF_SIGLA)
    municipios = municipios[
        ["id_municip", "codigo_ibge", "nome", "uf", "latitude", "longitude", "capital"]
    ].set_index("id_municip")

    id_municip = bruto["ID_MUNICIP"]
    sem_municipio = id_municip.isna() | ~id_municip.isin(municipios.index)
    if sem_municipio.any():
        raise ValueError(
            f"{int(sem_municipio.sum())} notificações sem município correspondente em municipios.csv."
        )
    id_municip = id_municip.astype("int32")

    # Calcula a semana epidemiológica nas datas distintas (poucas centenas).
    datas_unicas = pd.Series(datas.unique())
    ano_u, semana_u, inicio_u = semana_epidemiologica(datas_unicas)
    posicao = pd.Index(datas_unicas).get_indexer(datas)
    ano_epi = ano_u.iloc[posicao].reset_index(drop=True)
    semana_epi = semana_u.iloc[posicao].reset_index(drop=True)
    inicio_semana = inicio_u.iloc[posicao].reset_index(drop=True)
    classi = _codigo(bruto["CLASSI_FIN"])
    evol = _codigo(bruto["EVOLUCAO"])
    hosp = _codigo(bruto["HOSPITALIZ"])

    df = pd.DataFrame(
        {
            "data": datas.to_numpy(),
            "mes": datas.dt.to_period("M").dt.to_timestamp().to_numpy(),
            "ano_epi": ano_epi.to_numpy(),
            "semana_epi": semana_epi.to_numpy(),
            "inicio_semana": inicio_semana.to_numpy(),
            "id_municip": id_municip.to_numpy(),
            "uf": pd.Categorical(municipios["uf"].reindex(id_municip.to_numpy()).to_numpy()),
            "classi": classi,
            "evolucao": evol,
            "hospitaliz": hosp,
        }
    )
    df["confirmado"] = np.isin(classi, CONFIRMADOS)
    df["grave"] = np.isin(classi, (11, 12))
    df["obito_dengue"] = evol == 2  # definição da camada Ouro (gerar_gold.py)
    df["obito_investigacao"] = evol == 4
    df["hospitalizado"] = hosp == 1

    arquivos = tuple(
        (a.name, a.stat().st_size, a.stat().st_mtime) for a in (arquivo_25, arquivo_26, arquivo_mun)
    )
    return Dataset(
        notificacoes=df,
        municipios=municipios,
        carregado_em=datetime.now(timezone.utc),
        arquivos=arquivos,
        linhas_descartadas={
            "DENGBR25 com NU_ANO fora de 2024–2025": fora_do_ano,
            "DT_NOTIFIC inválida": invalidas,
            "DT_NOTIFIC posterior à data de processamento": futuras,
        },
        colunas_disponiveis=colunas_disponiveis,
    )
