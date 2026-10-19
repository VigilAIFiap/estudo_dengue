from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pandas as pd

from src.con_db import con_sql

from .dataset import (
    COLUNAS,
    Dataset,
    _carregar_municipios,
    _normalizar_notificacoes,
)

LOGGER = logging.getLogger(__name__)
FETCH_SIZE = 50_000
PRATA_COLUMNS = (
    "DT_NOTIFIC",
    "ID_MUNICIP",
    "HOSPITALIZ",
    "CLASSI_FIN",
    "EVOLUCAO",
)
CLASSIFICATION_CODES = {
    "dengue": 10,
    "dengue_com_sinais_de_alarme": 11,
    "dengue_grave": 12,
    "chikungunya": 13,
    "descartado": 5,
    "inconclusivo": 8,
    "ignorado": 9,
    "codigo_0_nao_documentado": 0,
}
EVOLUTION_CODES = {
    "cura": 1,
    "obito_dengue": 2,
    "obito_outra_causa": 3,
    "obito_em_investigacao": 4,
    "ignorado": 9,
    "codigo_0_nao_documentado": 0,
}


def _table_name(value: str) -> str:
    table = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_$#]{0,29}", table):
        raise ValueError(f"Nome de tabela Oracle inválido: {value!r}")
    return table


def _restore_codes(values: pd.Series, mapping: dict[str, int]) -> pd.Series:
    labels = values.astype("string").str.strip().str.lower()
    numeric = pd.to_numeric(labels, errors="coerce")
    return numeric.fillna(labels.map(mapping))


def carregar_oracle(
    municipalities_path: Path,
    table_name: str | None = None,
    hoje: pd.Timestamp | None = None,
) -> Dataset:
    """Load the API's required notification fields from Oracle PRATA at startup."""
    table = _table_name(
        table_name or os.environ.get("ORACLE_API_TABLE", "PRATA")
    )
    columns_sql = ", ".join(PRATA_COLUMNS)
    query = (
        f"SELECT {columns_sql} FROM {table} "
        "WHERE DT_NOTIFIC >= DATE '2024-01-01'"
    )
    bronze_23_path = Path(municipalities_path).parent / "DENGBR23.csv"
    if not bronze_23_path.is_file():
        raise FileNotFoundError(
            f"Fonte completa de 2023 não encontrada: {bronze_23_path}"
        )
    municipios = _carregar_municipios(Path(municipalities_path))
    reference_date = (hoje or pd.Timestamp.today()).normalize()
    notificacoes: list[pd.DataFrame] = []
    invalidas = 0
    futuras = 0
    bronze_23_rows = 0

    bronze_23_chunks = pd.read_csv(
        bronze_23_path,
        encoding="latin-1",
        usecols=COLUNAS,
        dtype={
            "DT_NOTIFIC": str,
            "NU_ANO": str,
            "SG_UF_NOT": str,
            "ID_MUNICIP": "float64",
            "HOSPITALIZ": "float32",
            "CLASSI_FIN": "float32",
            "EVOLUCAO": "float32",
        },
        chunksize=250_000,
    )
    fora_do_ano_23 = 0
    for chunk in bronze_23_chunks:
        year_mask = chunk["NU_ANO"].eq("2023")
        fora_do_ano_23 += int((~year_mask).sum())
        selected = chunk.loc[year_mask, COLUNAS]
        if selected.empty:
            continue
        dates = pd.to_datetime(
            selected["DT_NOTIFIC"], format="%Y-%m-%d", errors="coerce"
        )
        invalidas += int(dates.isna().sum())
        futuras += int(dates.gt(reference_date).sum())
        valid = dates.notna() & dates.le(reference_date)
        if valid.any():
            bronze_23_rows += int(valid.sum())
            notificacoes.append(
                _normalizar_notificacoes(
                    selected.loc[valid],
                    dates.loc[valid],
                    municipios,
                )
            )

    conn, status = con_sql()
    if conn is None:
        raise RuntimeError(f"Não foi possível conectar a API ao Oracle: {status}")

    total = 0
    try:
        with conn.cursor() as cursor:
            cursor.arraysize = FETCH_SIZE
            cursor.execute(query)
            while rows := cursor.fetchmany(FETCH_SIZE):
                batch = pd.DataFrame.from_records(rows, columns=PRATA_COLUMNS)
                total += len(rows)
                if total % 500_000 < FETCH_SIZE:
                    LOGGER.info("API: %s notificações lidas da tabela %s.", f"{total:,}", table)
                batch["CLASSI_FIN"] = _restore_codes(
                    batch["CLASSI_FIN"], CLASSIFICATION_CODES
                )
                batch["EVOLUCAO"] = _restore_codes(
                    batch["EVOLUCAO"], EVOLUTION_CODES
                )
                dates = pd.to_datetime(batch["DT_NOTIFIC"], errors="coerce")
                invalidas += int(dates.isna().sum())
                futuras += int(dates.gt(reference_date).sum())
                valid = dates.notna() & dates.le(reference_date)
                if valid.any():
                    notificacoes.append(
                        _normalizar_notificacoes(
                            batch.loc[valid],
                            dates.loc[valid],
                            municipios,
                        )
                    )
    finally:
        conn.close()

    if not total and not bronze_23_rows:
        LOGGER.warning(
            "Não há notificações de 2023 no CSV nem notificações desde 2024 na tabela %s.",
            table,
        )
    if not notificacoes:
        raise ValueError("A fonte Oracle e o CSV não contêm notificações válidas.")
    dataset_frame = pd.concat(notificacoes, ignore_index=True)

    LOGGER.info(
        "API: %s notificações de 2023 do CSV + %s linhas de %s; "
        "%s datas inválidas e %s futuras descartadas.",
        f"{bronze_23_rows:,}",
        f"{total:,}",
        table,
        f"{invalidas:,}",
        f"{futuras:,}",
    )
    return Dataset(
        notificacoes=dataset_frame,
        municipios=municipios,
        carregado_em=pd.Timestamp.now(tz="UTC").to_pydatetime(),
        arquivos=(),
        linhas_descartadas={
            "DENGBR23 com NU_ANO diferente de 2023": fora_do_ano_23,
            "DT_NOTIFIC inválida": invalidas,
            "DT_NOTIFIC posterior à data de processamento": futuras,
        },
        colunas_disponiveis=PRATA_COLUMNS,
    )
