from __future__ import annotations

import os
from typing import Any

from src.con_db import con_sql

from .schemas import PatientAssessmentSubmission


def save_assessment(assessment: PatientAssessmentSubmission) -> int:
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
            connection.commit()
            return int(value)
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
