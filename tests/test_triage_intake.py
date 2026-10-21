from __future__ import annotations

import unittest
from unittest.mock import patch

from api.schemas import PatientAssessmentSubmission
from api.triage_intake import save_assessment


class FakeVariable:
    def getvalue(self):
        return [73]


class FakeCursor:
    def __init__(self, schema="VIGIL_APEX"):
        self.schema = schema
        self.result = None
        self.insert_binds = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, binds=None):
        if "SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')" in statement:
            self.result = (self.schema,)
        else:
            self.insert_binds = binds

    def fetchone(self):
        return self.result

    def var(self, _type):
        return FakeVariable()


class FakeConnection:
    def __init__(self, schema="VIGIL_APEX"):
        self.cursor_instance = FakeCursor(schema)
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
            intake_id = save_assessment(
                PatientAssessmentSubmission(age_group="20-39", fever="SIM")
            )

        self.assertEqual(intake_id, 73)
        self.assertEqual(connection.cursor_instance.insert_binds["age_group"], "20-39")
        self.assertEqual(connection.cursor_instance.insert_binds["fever"], "SIM")
        self.assertIsNone(connection.cursor_instance.insert_binds["sex"])
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

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
