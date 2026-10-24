from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auditar_fontes import auditar_fontes


class SourceAuditTests(unittest.TestCase):
    def test_reports_annual_mismatches_invalid_and_future_dates(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for year in (2023, 2024, 2025, 2026):
                path = directory / f"DENGBR{year % 100:02d}.csv"
                if year == 2023:
                    path.write_text(
                        "NU_ANO,DT_NOTIFIC\n"
                        "2023,2023-01-01\n"
                        "2023,2023-01-31\n"
                        "2023,2024-02-01\n"
                        "2023,bad-date\n"
                        "2024,2023-03-01\n",
                        encoding="utf-8",
                    )
                else:
                    path.write_text(
                        "NU_ANO,DT_NOTIFIC\n"
                        f"{year},{year}-01-01\n",
                        encoding="utf-8",
                    )

            result = auditar_fontes(
                directory,
                as_of=pd.Timestamp("2023-12-31"),
            )[2023]

        self.assertEqual(result["linhas_total"], 5)
        self.assertEqual(result["linhas_ano"], 4)
        self.assertEqual(result["linhas_outros_anos"], 1)
        self.assertEqual(result["datas_invalidas"], 1)
        self.assertEqual(result["ano_data_divergente"], 1)
        self.assertEqual(result["datas_futuras"], 1)
        self.assertEqual(result["meses"], {"2023-01": 2})

    def test_requires_all_local_annual_csvs(self):
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(FileNotFoundError, "DENGBR23.csv"):
                auditar_fontes(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
