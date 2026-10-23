from __future__ import annotations

import unittest
from unittest.mock import patch

from api.schemas import PatientAssessmentSubmission
from api.triage_intake import AssessmentResult, save_assessment


class FakeVariable:
    def getvalue(self):
        return [73]


class FakeCursor:
    def __init__(
        self,
        schema="VIGIL_APEX",
        status="PENDENTE",
        queue_row=(None, None),
        queue_error=None,
    ):
        self.schema = schema
        self.status = status
        self.queue_row = queue_row
        self.queue_error = queue_error
        self.result = None
        self.insert_binds = None
        self.queue_queried = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, binds=None):
        if "SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')" in statement:
            self.result = (self.schema,)
        elif "INSERT INTO VIGIL_TRIAGE_INTAKE" in statement:
            self.insert_binds = binds
        elif "SELECT STATUS FROM VIGIL_TRIAGE_INTAKE" in statement:
            self.result = (self.status,)
        elif "FROM VIGIL_TRIAGE_REVIEW_QUEUE" in statement:
            self.queue_queried = True
            if self.queue_error:
                raise self.queue_error
            self.result = self.queue_row

    def fetchone(self):
        return self.result

    def var(self, _type):
        return FakeVariable()


class FakeConnection:
    def __init__(self, schema="VIGIL_APEX", **cursor_options):
        self.cursor_instance = FakeCursor(schema, **cursor_options)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class TriageIntakeTests(unittest.TestCase):
    def test_saves_allowlisted_form_data_and_commits(self):
        connection = FakeConnection()
        with patch("api.triage_intake.con_sql", return_value=(connection, "ok")):
            result = save_assessment(
                PatientAssessmentSubmission(age_group="20-39", fever="SIM")
            )

        self.assertEqual(result.intake_id, 73)
        self.assertEqual(connection.cursor_instance.insert_binds["age_group"], "20-39")
        self.assertEqual(connection.cursor_instance.insert_binds["fever"], "SIM")
        self.assertIsNone(connection.cursor_instance.insert_binds["sex"])
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_auto_approved_record_reports_status_without_details(self):
        connection = FakeConnection(status="APROVADO")
        with patch("api.triage_intake.con_sql", return_value=(connection, "ok")):
            result = save_assessment(PatientAssessmentSubmission(age_group="20-39"))

        self.assertEqual(
            result,
            AssessmentResult(intake_id=73, status="APROVADO"),
        )
        self.assertFalse(connection.cursor_instance.queue_queried)
        self.assertTrue(connection.committed)

    def test_pending_record_reports_missing_fields_and_inconsistencies(self):
        connection = FakeConnection(
            status="PENDENTE",
            queue_row=("FEBRE, GESTACAO", "GESTACAO_INCOMPATIVEL_COM_SEXO"),
        )
        with patch("api.triage_intake.con_sql", return_value=(connection, "ok")):
            result = save_assessment(PatientAssessmentSubmission(sex="M"))

        self.assertEqual(result.status, "PENDENTE")
        self.assertEqual(result.missing_fields, ("FEBRE", "GESTACAO"))
        self.assertEqual(result.inconsistencies, ("GESTACAO_INCOMPATIVEL_COM_SEXO",))
        self.assertTrue(connection.committed)

    def test_falls_back_to_pending_when_review_view_is_not_migrated(self):
        connection = FakeConnection(queue_error=RuntimeError("ORA-00904"))
        with patch("api.triage_intake.con_sql", return_value=(connection, "ok")):
            result = save_assessment(PatientAssessmentSubmission())

        self.assertEqual(result, AssessmentResult(intake_id=73, status="PENDENTE"))
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)

    def test_refuses_unexpected_schema_and_rolls_back(self):
        connection = FakeConnection(schema="OTHER_SCHEMA")
        with (
            patch("api.triage_intake.con_sql", return_value=(connection, "ok")),
            patch.dict("os.environ", {"VIGIL_DQ_SCHEMA": "VIGIL_APEX"}),
            self.assertRaisesRegex(RuntimeError, "Schema Oracle ativo"),
        ):
            save_assessment(PatientAssessmentSubmission())

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
