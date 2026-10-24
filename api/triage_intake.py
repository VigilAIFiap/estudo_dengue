from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.con_db import con_sql

from .schemas import PatientAssessmentSubmission


@dataclass(frozen=True)
class AssessmentResult:
    """Desfecho do envio: protocolo e o que a validação do Oracle decidiu."""

    intake_id: int
    status: str = "PENDENTE"
    missing_fields: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()


def _split_codes(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in str(value).split(",") if part.strip())


def _read_outcome(
    cursor: Any, intake_id: int
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Lê o status e, se o registro ficou em revisão, o motivo apontado pelo Oracle.

    O gatilho de aprovação automática roda dentro do INSERT, então esta leitura (na mesma
    transação, antes do commit) já enxerga o resultado. Se a migração do fluxo de aprovação
    ainda não foi aplicada, mantém o comportamento anterior: PENDENTE, sem detalhes. Um erro
    de SELECT no Oracle não desfaz o INSERT já feito.
    """
    try:
        cursor.execute(
            "SELECT STATUS FROM VIGIL_TRIAGE_INTAKE WHERE INTAKE_ID = :intake_id",
            {"intake_id": intake_id},
        )
        row = cursor.fetchone()
        status = str(row[0]) if row and row[0] else "PENDENTE"
        if status not in ("PENDENTE", "EM_ANALISE"):
            return status, (), ()

        cursor.execute(
            "SELECT CAMPOS_FALTANTES, INCONSISTENCIAS FROM VIGIL_TRIAGE_REVIEW_QUEUE "
            "WHERE INTAKE_ID = :intake_id",
            {"intake_id": intake_id},
        )
        row = cursor.fetchone()
        if not row:
            return status, (), ()
        return status, _split_codes(row[0]), _split_codes(row[1])
    except Exception:
        return "PENDENTE", (), ()


def save_assessment(assessment: PatientAssessmentSubmission) -> AssessmentResult:
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
                    "Envio cancelado para evitar gravar no schema errado."
                )

            intake_id = cursor.var(int)
            cursor.execute(
                """
                INSERT INTO VIGIL_TRIAGE_INTAKE (
                    AGE_GROUP, SEX, SYMPTOM_DURATION,
                    FEVER, HEADACHE, MUSCLE_PAIN, RASH, NAUSEA, VOMITING,
                    PREGNANCY, COMORBIDITIES
                ) VALUES (
                    :age_group, :sex, :symptom_duration,
                    :fever, :headache, :muscle_pain, :rash, :nausea, :vomiting,
                    :pregnancy, :comorbidities
                )
                RETURNING INTAKE_ID INTO :intake_id
                """,
                {
                    **assessment.model_dump(),
                    "intake_id": intake_id,
                },
            )
            value: Any = intake_id.getvalue()
            if isinstance(value, (list, tuple)):
                value = value[0]
            if value is None:
                raise RuntimeError("Oracle não retornou o protocolo do atendimento.")
            protocol = int(value)
            status, missing, inconsistencies = _read_outcome(cursor, protocol)
            connection.commit()
            return AssessmentResult(
                intake_id=protocol,
                status=status,
                missing_fields=missing,
                inconsistencies=inconsistencies,
            )
    except Exception as error:
        try:
            connection.rollback()
        except Exception as rollback_error:
            raise RuntimeError(
                "O envio falhou e o rollback também falhou; verifique a fila de avaliação "
                f"no APEX antes de tentar novamente. Erro original: {error}; "
                f"erro no rollback: {rollback_error}"
            ) from error
        raise
    finally:
        connection.close()
