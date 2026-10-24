from __future__ import annotations

import argparse
import csv
import getpass
import os
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

if __package__:
    from .config import RAW
    from .con_db import con_sql
else:
    from config import RAW
    from con_db import con_sql


INPUT_COLUMNS = (
    "DT_NOTIFIC",
    "ID_MUNICIP",
    "IDADE_ANOS",
    "CS_SEXO",
    "CS_GESTANT",
    "FEBRE",
    "MIALGIA",
    "CEFALEIA",
    "EXANTEMA",
    "VOMITO",
    "NAUSEA",
    "DOR_COSTAS",
    "CONJUNTVIT",
    "ARTRITE",
    "ARTRALGIA",
    "PETEQUIA_N",
    "DOR_RETRO",
    "DIABETES",
    "HEMATOLOG",
    "HEPATOPAT",
    "RENAL",
    "HIPERTENSA",
    "ACIDO_PEPT",
    "AUTO_IMUNE",
)
REQUIRED_COLUMNS = {"DT_NOTIFIC", "ID_MUNICIP"}
MAX_LENGTHS = {
    "DT_NOTIFIC": 30,
    "ID_MUNICIP": 12,
    "IDADE_ANOS": 30,
    "CS_SEXO": 10,
    "CS_GESTANT": 20,
    **{
        column: 10
        for column in INPUT_COLUMNS
        if column not in {"DT_NOTIFIC", "ID_MUNICIP", "IDADE_ANOS", "CS_SEXO", "CS_GESTANT"}
    },
}
RULE_CODES = (
    "DT_NOTIFIC_INVALIDA",
    "DT_NOTIFIC_FUTURA",
    "IDADE_FORA_INTERVALO",
    "MUNICIPIO_NAO_RECONHECIDO",
)
RECORD_INSERT = """
    INSERT INTO VIGIL_DQ_RECORD (
        BATCH_ID, SOURCE_ROW, DT_NOTIFIC, ID_MUNICIP, IDADE_ANOS,
        CS_SEXO, CS_GESTANT, FEBRE, MIALGIA, CEFALEIA, EXANTEMA,
        VOMITO, NAUSEA, DOR_COSTAS, CONJUNTVIT, ARTRITE, ARTRALGIA,
        PETEQUIA_N, DOR_RETRO, DIABETES, HEMATOLOG, HEPATOPAT, RENAL,
        HIPERTENSA, ACIDO_PEPT, AUTO_IMUNE
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13,
        :14, :15, :16, :17, :18, :19, :20, :21, :22, :23, :24, :25, :26
    )
"""
FINDING_INSERT = """
    INSERT INTO VIGIL_DQ_FINDING (
        BATCH_ID, REGISTRO_ID, RULE_CODE, FIELD_NAME, SEVERITY, MESSAGE
    ) VALUES (:1, :2, :3, :4, :5, :6)
"""


class CsvInputError(ValueError):
    pass


def _municipality_ids(path: Path) -> set[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Dimensão de municípios não encontrada: {path}")
    try:
        import pandas as pd

        municipios = pd.read_csv(path, usecols=["codigo_ibge"])
        values = pd.to_numeric(municipios["codigo_ibge"], errors="raise")
        return {str(int(value) // 10) for value in values}
    except (KeyError, ValueError, OSError) as error:
        raise CsvInputError(
            f"Não foi possível ler codigo_ibge em {path}: {error}"
        ) from error


def _parse_notification_date(raw_value: str | None) -> date | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def _findings_for_row(
    record: dict[str, str | None],
    municipalities: set[str],
    reference_date: date,
) -> list[tuple[str, str, str]]:
    findings = []
    notification_date = _parse_notification_date(record["DT_NOTIFIC"])
    if notification_date is None:
        findings.append(
            (
                "DT_NOTIFIC_INVALIDA",
                "DT_NOTIFIC",
                "Data ausente ou inválida; use AAAA-MM-DD ou DD/MM/AAAA.",
            )
        )
    elif notification_date > reference_date:
        findings.append(
            (
                "DT_NOTIFIC_FUTURA",
                "DT_NOTIFIC",
                "Data de notificação posterior à data de validação.",
            )
        )

    age = (record["IDADE_ANOS"] or "").strip()
    if age:
        try:
            parsed_age = Decimal(age.replace(",", "."))
        except InvalidOperation:
            parsed_age = Decimal("NaN")
        if not parsed_age.is_finite() or not Decimal(0) <= parsed_age <= Decimal(120):
            findings.append(
                (
                    "IDADE_FORA_INTERVALO",
                    "IDADE_ANOS",
                    "Idade preenchida não é numérica ou está fora do intervalo de 0 a 120.",
                )
            )

    municipality = (record["ID_MUNICIP"] or "").strip()
    if not municipality or municipality not in municipalities:
        findings.append(
            (
                "MUNICIPIO_NAO_RECONHECIDO",
                "ID_MUNICIP",
                "Código municipal ausente ou não encontrado em municipios.csv.",
            )
        )
    return findings


def _iter_csv_batches(
    path: Path,
    municipalities: set[str],
    reference_date: date,
    encoding: str,
    batch_size: int,
) -> Iterator[tuple[list[tuple[int, dict[str, str | None]]], dict[int, list[tuple[str, str, str]]]]]:
    if batch_size < 1:
        raise ValueError("O tamanho do lote deve ser maior que zero.")
    with path.open("r", encoding=encoding, newline="") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames
        if not headers:
            raise CsvInputError("O CSV está vazio ou não possui cabeçalho.")
        if len(headers) != len(set(headers)):
            raise CsvInputError("O CSV possui nomes de coluna repetidos.")
        missing = REQUIRED_COLUMNS.difference(headers)
        if missing:
            raise CsvInputError(
                f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}."
            )
        unexpected = set(headers).difference(INPUT_COLUMNS)
        if unexpected:
            raise CsvInputError(
                "O CSV contém colunas fora do escopo permitido; remova: "
                + ", ".join(sorted(unexpected))
            )

        batch: list[tuple[int, dict[str, str | None]]] = []
        row_findings: dict[int, list[tuple[str, str, str]]] = {}
        source_row = 1
        for raw in reader:
            source_row += 1
            if None in raw:
                raise CsvInputError(
                    f"Linha CSV {source_row} possui mais valores que o cabeçalho."
                )
            record = {}
            for column in INPUT_COLUMNS:
                value = raw.get(column)
                normalized = value.strip() if value is not None else ""
                if len(normalized) > MAX_LENGTHS[column]:
                    raise CsvInputError(
                        f"Linha CSV {source_row}: {column} excede "
                        f"{MAX_LENGTHS[column]} caracteres."
                    )
                record[column] = normalized or None
            batch.append((source_row, record))
            findings = _findings_for_row(record, municipalities, reference_date)
            if findings:
                row_findings[source_row] = findings
            if len(batch) >= batch_size:
                yield batch, row_findings
                batch = []
                row_findings = {}
        if batch:
            yield batch, row_findings


def preview_csv(
    path: Path,
    municipalities_path: Path = RAW / "municipios.csv",
    reference_date: date | None = None,
    encoding: str = "utf-8-sig",
    batch_size: int = 1000,
) -> dict[str, int]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")
    municipalities = _municipality_ids(Path(municipalities_path))
    rules = Counter()
    total_rows = 0
    for rows, findings in _iter_csv_batches(
        csv_path,
        municipalities,
        reference_date or date.today(),
        encoding,
        batch_size,
    ):
        total_rows += len(rows)
        for row_findings in findings.values():
            rules.update(rule_code for rule_code, _, _ in row_findings)
    if total_rows == 0:
        raise CsvInputError("O CSV não contém registros para importar.")
    return {"linhas": total_rows, **dict(sorted(rules.items()))}


def import_csv(
    path: Path,
    municipalities_path: Path = RAW / "municipios.csv",
    reference_date: date | None = None,
    encoding: str = "utf-8-sig",
    batch_size: int = 500,
    created_by: str | None = None,
    source_name: str | None = None,
) -> tuple[int, dict[str, int]]:
    if batch_size < 1:
        raise ValueError("O tamanho do lote deve ser maior que zero.")
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")
    municipalities = _municipality_ids(Path(municipalities_path))
    as_of = reference_date or date.today()
    connection, status = con_sql()
    if connection is None:
        raise RuntimeError(f"Não foi possível conectar ao Oracle: {status}")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL"
            )
            current_schema = cursor.fetchone()
            expected_schema = os.environ.get(
                "VIGIL_DQ_SCHEMA", "VIGIL_APEX"
            ).strip().upper()
            if (
                not current_schema
                or not current_schema[0]
                or str(current_schema[0]).upper() != expected_schema
            ):
                actual_schema = str(current_schema[0]) if current_schema else "desconhecido"
                raise RuntimeError(
                    f"Schema Oracle ativo é {actual_schema}; esperado {expected_schema}. "
                    "A importação foi cancelada para evitar gravar no schema errado."
                )

            cursor.execute(
                """
                SELECT RULE_CODE, SEVERITY
                FROM VIGIL_DQ_RULE
                WHERE ACTIVE = 'S'
                """
            )
            active_rules = dict(cursor.fetchall())
            missing_rules = set(RULE_CODES).difference(active_rules)
            if missing_rules:
                raise RuntimeError(
                    "Regras ausentes/inativas no Oracle: "
                    + ", ".join(sorted(missing_rules))
                    + ". Execute ou revise sql/create_data_quality_tables.sql."
                )

            batch_id_var = cursor.var(int)
            cursor.execute(
                """
                INSERT INTO VIGIL_DQ_BATCH (SOURCE_NAME, CREATED_BY)
                VALUES (:source_name, :created_by)
                RETURNING BATCH_ID INTO :batch_id
                """,
                {
                    "source_name": source_name or csv_path.name,
                    "created_by": created_by or getpass.getuser(),
                    "batch_id": batch_id_var,
                },
            )
            batch_id_value = batch_id_var.getvalue()
            if isinstance(batch_id_value, (list, tuple)):
                batch_id_value = batch_id_value[0]
            if batch_id_value is None:
                raise RuntimeError("Oracle não retornou o identificador do lote.")
            batch_id = int(batch_id_value)
            row_count = 0
            finding_counts: Counter[str] = Counter()

            for rows, findings_by_source_row in _iter_csv_batches(
                csv_path,
                municipalities,
                as_of,
                encoding,
                batch_size,
            ):
                record_binds = [
                    (batch_id, source_row, *(record[column] for column in INPUT_COLUMNS))
                    for source_row, record in rows
                ]
                cursor.executemany(RECORD_INSERT, record_binds)
                first_row = rows[0][0]
                last_row = rows[-1][0]
                cursor.execute(
                    """
                    SELECT REGISTRO_ID, SOURCE_ROW
                    FROM VIGIL_DQ_RECORD
                    WHERE BATCH_ID = :batch_id
                      AND SOURCE_ROW BETWEEN :first_row AND :last_row
                    ORDER BY SOURCE_ROW
                    """,
                    {
                        "batch_id": batch_id,
                        "first_row": first_row,
                        "last_row": last_row,
                    },
                )
                record_ids = {
                    int(source_row): int(record_id)
                    for record_id, source_row in cursor.fetchall()
                }
                finding_binds = []
                for source_row, row_findings in findings_by_source_row.items():
                    if source_row not in record_ids:
                        raise RuntimeError(
                            "Não foi possível relacionar ocorrência à linha "
                            f"{source_row} do lote {batch_id}."
                        )
                    for rule_code, field_name, message in row_findings:
                        finding_binds.append(
                            (
                                batch_id,
                                record_ids[source_row],
                                rule_code,
                                field_name,
                                active_rules[rule_code],
                                message,
                            )
                        )
                        finding_counts[rule_code] += 1
                if finding_binds:
                    cursor.executemany(FINDING_INSERT, finding_binds)
                row_count += len(rows)

            cursor.execute(
                """
                UPDATE VIGIL_DQ_BATCH
                SET FINISHED_AT = SYSTIMESTAMP,
                    STATUS = 'CONCLUIDO',
                    ROW_COUNT = :row_count,
                    FINDING_COUNT = :finding_count
                WHERE BATCH_ID = :batch_id
                """,
                {
                    "row_count": row_count,
                    "finding_count": sum(finding_counts.values()),
                    "batch_id": batch_id,
                },
            )
        connection.commit()
    except Exception as error:
        try:
            connection.rollback()
        except Exception as rollback_error:
            raise RuntimeError(
                "A importação falhou e o rollback também falhou; "
                "verifique o estado do lote no Oracle antes de tentar novamente. "
                f"Erro original: {error}; erro no rollback: {rollback_error}"
            ) from error
        raise
    finally:
        connection.close()

    return batch_id, {"linhas": row_count, **dict(sorted(finding_counts.items()))}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida CSV de entrada e, com confirmação, grava lote e ocorrências no Oracle."
    )
    parser.add_argument("--file", required=True, type=Path, help="CSV local para prévia/importação.")
    parser.add_argument(
        "--municipalities",
        type=Path,
        default=RAW / "municipios.csv",
        help="Dimensão municipios.csv usada para validar ID_MUNICIP.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Codificação do CSV (padrão: utf-8-sig; use latin-1 se necessário).",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--confirm-import",
        action="store_true",
        help="Grava o conteúdo sensível no Oracle; sem esta opção, somente prévia local.",
    )
    args = parser.parse_args()

    preview = preview_csv(
        args.file,
        args.municipalities,
        encoding=args.encoding,
        batch_size=args.batch_size,
    )
    print("Prévia local (nenhum dado gravado):")
    for key, value in preview.items():
        print(f"  {key}: {value:,}")
    if not args.confirm_import:
        print("Para importar depois de revisar, acrescente --confirm-import.")
        return

    batch_id, result = import_csv(
        args.file,
        args.municipalities,
        encoding=args.encoding,
        batch_size=args.batch_size,
    )
    print(f"Lote Oracle {batch_id} importado e confirmado:")
    for key, value in result.items():
        print(f"  {key}: {value:,}")


if __name__ == "__main__":
    main()
