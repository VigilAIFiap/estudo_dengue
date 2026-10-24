"""Carga única e normalização das notificações SINAN para a API.

Regras de leitura da base:
- DENGBR23.csv: somente NU_ANO 2023 (fonte completa local);
- DENGBR24.csv: somente NU_ANO 2024 (fonte completa local);
- DENGBR25.csv: somente NU_ANO 2025;
- DENGBR26.csv: somente NU_ANO 2026;
- descarta DT_NOTIFIC inválida ou futura.

A UF é derivada do código IBGE do município usado na análise (dimensão
municipios.csv), não de SG_UF_NOT, que mistura códigos e siglas.

Município da análise (variável DENGUE_MUNICIPIO_BASE):
- "notificacao" (padrão): ID_MUNICIP, onde fica a unidade de saúde que notificou;
- "residencia": ID_MN_RESI, onde o paciente mora. Notificações sem residência
  válida no cadastro usam o município de notificação e são contadas em
  Dataset.sem_residencia.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

COLUNAS = [
    "DT_NOTIFIC", "NU_ANO", "SG_UF_NOT", "ID_MUNICIP",
    "HOSPITALIZ", "CLASSI_FIN", "EVOLUCAO",
]

BASES_MUNICIPAIS = ("notificacao", "residencia")
RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def caminho_municipios(data_dir: Path) -> Path:
    """municipios.csv a usar: MUNICIPIOS_CSV, o da pasta de dados ou a cópia versionada em api/data.

    A cópia versionada permite hospedar a API (DATA_SOURCE=oracle) sem os CSVs de notificações,
    que não vão para o git.
    """
    explicito = os.environ.get("MUNICIPIOS_CSV", "").strip()
    if explicito:
        return Path(explicito)
    local = Path(data_dir) / "municipios.csv"
    return local if local.exists() else RAIZ_PROJETO / "api" / "data" / "municipios.csv"


def base_municipal_configurada() -> str:
    base = os.environ.get("DENGUE_MUNICIPIO_BASE", "notificacao").strip().lower()
    if base not in BASES_MUNICIPAIS:
        raise ValueError(
            f"DENGUE_MUNICIPIO_BASE inválido: {base!r}. Use 'notificacao' ou 'residencia'."
        )
    return base


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
    base_municipal: str = "notificacao"
    sem_residencia: int = 0  # notificações que usaram o município de notificação por falta de residência válida


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


def _revisar_fonte(
    arquivo: Path,
    ano_esperado: int,
    hoje: pd.Timestamp,
) -> tuple[int, int, int, int]:
    registros_validos = 0
    outros_anos = 0
    datas_invalidas = 0
    datas_futuras = 0
    for chunk in pd.read_csv(
        arquivo,
        encoding="latin-1",
        usecols=["DT_NOTIFIC", "NU_ANO"],
        dtype={"DT_NOTIFIC": str, "NU_ANO": str},
        chunksize=250_000,
    ):
        year_mask = chunk["NU_ANO"].eq(str(ano_esperado))
        outros_anos += int((~year_mask).sum())
        selected = chunk.loc[year_mask]
        dates = pd.to_datetime(
            selected["DT_NOTIFIC"],
            format="%Y-%m-%d",
            errors="coerce",
        )
        mismatch = dates.notna() & dates.le(hoje) & dates.dt.year.ne(ano_esperado)
        if mismatch.any():
            raise ValueError(
                f"{arquivo.name} contém registros com NU_ANO={ano_esperado} "
                "e ano de DT_NOTIFIC diferente."
            )
        datas_invalidas += int(dates.isna().sum())
        datas_futuras += int(dates.gt(hoje).sum())
        registros_validos += int((dates.notna() & dates.le(hoje)).sum())
    return registros_validos, outros_anos, datas_invalidas, datas_futuras


def _carregar_municipios(arquivo_municipios: Path) -> pd.DataFrame:
    municipios = pd.read_csv(arquivo_municipios)
    municipios["id_municip"] = (
        municipios["codigo_ibge"].astype("int64") // 10
    ).astype("int32")
    if municipios["id_municip"].duplicated().any():
        raise ValueError("municipios.csv possui códigos municipais repetidos.")
    municipios["uf"] = municipios["codigo_uf"].map(UF_SIGLA)
    municipios = municipios[
        ["id_municip", "codigo_ibge", "nome", "uf", "latitude", "longitude", "capital"]
    ].set_index("id_municip")
    return municipios


def _normalizar_notificacoes(
    bruto: pd.DataFrame,
    datas: pd.Series,
    municipios: pd.DataFrame,
    base_municipal: str = "notificacao",
) -> pd.DataFrame:
    if bruto.empty:
        return pd.DataFrame()
    id_municip = pd.to_numeric(bruto["ID_MUNICIP"], errors="coerce")
    sem_residencia = 0
    if base_municipal == "residencia":
        residencia = pd.to_numeric(bruto["ID_MN_RESI"], errors="coerce")
        residencia_valida = residencia.notna() & residencia.isin(municipios.index)
        sem_residencia = int((~residencia_valida).sum())
        id_municip = residencia.where(residencia_valida, id_municip)
    sem_municipio = id_municip.isna() | ~id_municip.isin(municipios.index)
    if sem_municipio.any():
        raise ValueError(
            f"{int(sem_municipio.sum())} notificações sem município correspondente em municipios.csv."
        )
    id_municip = id_municip.astype("int32")

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
    df["obito_dengue"] = evol == 2
    df["obito_investigacao"] = evol == 4
    df["hospitalizado"] = hosp == 1
    df.attrs["sem_residencia"] = sem_residencia
    return df


def _montar_dataset(
    bruto: pd.DataFrame,
    datas: pd.Series,
    arquivo_municipios: Path,
    arquivos: tuple[tuple[str, int, float], ...],
    linhas_descartadas: dict[str, int],
    colunas_disponiveis: tuple[str, ...],
    base_municipal: str = "notificacao",
) -> Dataset:
    if bruto.empty:
        raise ValueError("A fonte não contém notificações com data válida.")
    municipios = _carregar_municipios(arquivo_municipios)
    notificacoes = _normalizar_notificacoes(bruto, datas, municipios, base_municipal)
    return Dataset(
        notificacoes=notificacoes,
        municipios=municipios,
        carregado_em=datetime.now(timezone.utc),
        arquivos=arquivos,
        linhas_descartadas=linhas_descartadas,
        colunas_disponiveis=colunas_disponiveis,
        base_municipal=base_municipal,
        sem_residencia=int(notificacoes.attrs.get("sem_residencia", 0)),
    )


def carregar(data_dir: Path, hoje: pd.Timestamp | None = None) -> Dataset:
    hoje = (hoje or pd.Timestamp.today()).normalize()
    arquivo_23 = data_dir / "DENGBR23.csv"
    arquivo_24 = data_dir / "DENGBR24.csv"
    arquivo_25 = data_dir / "DENGBR25.csv"
    arquivo_26 = data_dir / "DENGBR26.csv"
    arquivo_mun = data_dir / "municipios.csv"
    for arquivo in (arquivo_23, arquivo_24, arquivo_25, arquivo_26, arquivo_mun):
        if not arquivo.exists():
            raise FileNotFoundError(f"Arquivo de dados ausente: {arquivo}")

    colunas_disponiveis = tuple(
        sorted(
            set(_cabecalho(arquivo_23))
            | set(_cabecalho(arquivo_24))
            | set(_cabecalho(arquivo_25))
            | set(_cabecalho(arquivo_26))
        )
    )

    municipios = _carregar_municipios(arquivo_mun)
    sources = (
        (arquivo_23, 2023),
        (arquivo_24, 2024),
        (arquivo_25, 2025),
        (arquivo_26, 2026),
    )
    base_municipal = base_municipal_configurada()
    colunas = list(COLUNAS)
    if base_municipal == "residencia":
        for arquivo, _ in sources:
            if "ID_MN_RESI" not in _cabecalho(arquivo):
                raise ValueError(
                    f"{arquivo.name} não tem a coluna ID_MN_RESI, exigida por "
                    "DENGUE_MUNICIPIO_BASE=residencia."
                )
        colunas.append("ID_MN_RESI")
    file_signatures = {
        arquivo: (arquivo.stat().st_size, arquivo.stat().st_mtime_ns)
        for arquivo, _ in sources
    }
    reviewed = {
        arquivo: _revisar_fonte(arquivo, year, hoje)
        for arquivo, year in sources
    }
    expected_rows = sum(counts[0] for counts in reviewed.values())
    if expected_rows == 0:
        raise ValueError("As fontes não contêm notificações com data válida.")

    uf_categories = tuple(UF_SIGLA.values())
    uf_codes = {value: code for code, value in enumerate(uf_categories)}
    arrays = {
        "data": np.empty(expected_rows, dtype="datetime64[ns]"),
        "mes": np.empty(expected_rows, dtype="datetime64[ns]"),
        "ano_epi": np.empty(expected_rows, dtype="int16"),
        "semana_epi": np.empty(expected_rows, dtype="int16"),
        "inicio_semana": np.empty(expected_rows, dtype="datetime64[ns]"),
        "id_municip": np.empty(expected_rows, dtype="int32"),
        "uf_codes": np.empty(expected_rows, dtype="int8"),
        "classi": np.empty(expected_rows, dtype="int8"),
        "evolucao": np.empty(expected_rows, dtype="int8"),
        "hospitaliz": np.empty(expected_rows, dtype="int8"),
        "confirmado": np.empty(expected_rows, dtype=bool),
        "grave": np.empty(expected_rows, dtype=bool),
        "obito_dengue": np.empty(expected_rows, dtype=bool),
        "obito_investigacao": np.empty(expected_rows, dtype=bool),
        "hospitalizado": np.empty(expected_rows, dtype=bool),
    }
    tipos = {
        "DT_NOTIFIC": str,
        "NU_ANO": str,
        "SG_UF_NOT": str,
        "ID_MUNICIP": "float64",
        "HOSPITALIZ": "float32",
        "CLASSI_FIN": "float32",
        "EVOLUCAO": "float32",
    }
    if base_municipal == "residencia":
        tipos["ID_MN_RESI"] = "float64"
    leitura = dict(sep=",", encoding="latin-1", usecols=colunas, dtype=tipos)
    cursor = 0
    sem_residencia = 0
    for arquivo, year in sources:
        for chunk in pd.read_csv(arquivo, chunksize=250_000, **leitura):
            selected = chunk.loc[chunk["NU_ANO"].eq(str(year)), colunas]
            if selected.empty:
                continue

            datas = pd.to_datetime(
                selected["DT_NOTIFIC"],
                format="%Y-%m-%d",
                errors="coerce",
            )
            validas = datas.notna() & datas.le(hoje)
            if not validas.any():
                continue
            normalizadas = _normalizar_notificacoes(
                selected.loc[validas],
                datas.loc[validas],
                municipios,
                base_municipal,
            )
            sem_residencia += int(normalizadas.attrs.get("sem_residencia", 0))
            end = cursor + len(normalizadas)
            for column in (
                "data", "mes", "ano_epi", "semana_epi", "inicio_semana",
                "id_municip", "classi", "evolucao", "hospitaliz",
                "confirmado", "grave", "obito_dengue",
                "obito_investigacao", "hospitalizado",
            ):
                arrays[column][cursor:end] = normalizadas[column].to_numpy()
            uf = normalizadas["uf"].astype("string").map(uf_codes)
            if uf.isna().any():
                raise ValueError("A dimensão municipal contém uma UF não reconhecida.")
            arrays["uf_codes"][cursor:end] = uf.to_numpy(dtype="int8")
            cursor = end

    changed_sources = [
        arquivo.name
        for arquivo, signature in file_signatures.items()
        if (arquivo.stat().st_size, arquivo.stat().st_mtime_ns) != signature
    ]
    if changed_sources:
        raise RuntimeError(
            "Arquivos de origem foram modificados durante a leitura: "
            + ", ".join(changed_sources)
        )
    if cursor != expected_rows:
        raise RuntimeError(
            f"A leitura em blocos esperava {expected_rows:,} linhas válidas, "
            f"mas processou {cursor:,}."
        )

    arrays["uf"] = pd.Categorical.from_codes(
        arrays.pop("uf_codes"),
        categories=uf_categories,
    )
    df = pd.DataFrame(arrays, copy=False)
    arquivos = tuple(
        (arquivo.name, arquivo.stat().st_size, arquivo.stat().st_mtime)
        for arquivo, _ in sources
    ) + ((arquivo_mun.name, arquivo_mun.stat().st_size, arquivo_mun.stat().st_mtime),)
    descartadas = {
        f"{arquivo.stem} com NU_ANO diferente de {year}": reviewed[arquivo][1]
        for arquivo, year in sources
    }
    descartadas["DT_NOTIFIC inválida"] = sum(
        counts[2] for counts in reviewed.values()
    )
    descartadas["DT_NOTIFIC posterior à data de processamento"] = sum(
        counts[3] for counts in reviewed.values()
    )
    return Dataset(
        notificacoes=df,
        municipios=municipios,
        carregado_em=datetime.now(timezone.utc),
        arquivos=arquivos,
        linhas_descartadas=descartadas,
        colunas_disponiveis=colunas_disponiveis,
        base_municipal=base_municipal,
        sem_residencia=sem_residencia,
    )
