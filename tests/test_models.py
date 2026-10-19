from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from modelos.pacientes import _labels, prepare_patient_features, train_patient_models
from modelos.series_temporais import (
    prepare_daily_cases,
    prepare_monthly_cases,
)


class ModelPreparationTests(unittest.TestCase):
    def test_monthly_series_counts_only_confirmed_cases_and_skips_partial_month(self):
        dates = pd.date_range('2025-01-01', '2026-04-01', freq='MS')
        frame = pd.DataFrame(
            {
                'DT_NOTIFIC': list(dates) + [pd.Timestamp('2026-04-12')],
                'CLASSI_FIN': ['dengue'] * len(dates) + ['descartado'],
            }
        )
        result = prepare_monthly_cases(
            frame,
            as_of=pd.Timestamp('2026-04-15'),
            min_months=12,
        )
        self.assertEqual(len(result), 15)
        self.assertEqual(int(result.sum()), len(dates) - 1)
        self.assertEqual(result.index[-1], pd.Timestamp('2026-03-01'))

    def test_current_sinan_classification_codes_are_consistent(self):
        labels = pd.Series(
            [
                'dengue',
                'dengue_com_sinais_de_alarme',
                'dengue_grave',
                'descartado',
                'inconclusivo',
                'codigo_0_nao_documentado',
                'chikungunya',
            ]
        )
        targets = _labels(pd.DataFrame({'CLASSI_FIN': labels}))
        self.assertEqual(targets.iloc[:4].tolist(), [1, 1, 1, 0])
        self.assertTrue(targets.iloc[4:6].isna().all())
        self.assertEqual(targets.iloc[6], 0)

        raw_codes = pd.DataFrame(
            {'DT_NOTIFIC': pd.to_datetime(['2025-01-01'] * 7),
             'CLASSI_FIN': [10, 11, 12, 5, 8, 0, 13]}
        )
        series = prepare_monthly_cases(
            raw_codes,
            as_of=pd.Timestamp('2025-03-01'),
            min_months=1,
        )
        self.assertEqual(int(series.loc['2025-01-01']), 3)

    def test_daily_series_rejects_stale_data(self):
        frame = pd.DataFrame(
            {
                'DT_SIN_PRI': pd.date_range('2025-01-01', '2026-05-09', freq='D'),
                'CLASSI_FIN': 'dengue',
            }
        )
        with self.assertRaisesRegex(ValueError, 'desatualizada'):
            prepare_daily_cases(frame, as_of=pd.Timestamp('2026-10-14'))

    def test_patient_features_decode_age_and_preserve_missing_values(self):
        frame = pd.DataFrame(
            {
                'NU_IDADE_N': [4010, 4407],
                'FEBRE': [1, None],
                'MIALGIA': [2, 1],
                'CEFALEIA': [1, 1],
            }
        )
        result = prepare_patient_features(frame)
        self.assertEqual(result.loc[0, 'IDADE_ANOS'], 10)
        self.assertTrue(pd.isna(result.loc[1, 'IDADE_ANOS']))
        self.assertTrue(pd.isna(result.loc[1, 'FEBRE']))

    def test_patient_models_use_temporal_holdout_and_return_metrics(self):
        rows = []
        dates = pd.date_range('2025-01-01', periods=120, freq='D')
        for i, date in enumerate(dates):
            positive = i % 3 != 0
            rows.append(
                {
                    'DT_NOTIFIC': date,
                    'CLASSI_FIN': 'dengue' if positive else 'descartado',
                    'HOSPITALIZ': '1' if i % 5 == 0 else '2',
                    'IDADE_ANOS': 20 + i % 40,
                    'FEBRE': i % 2 + 1,
                    'MIALGIA': (i + 1) % 2 + 1,
                    'CEFALEIA': (i // 2) % 2 + 1,
                }
            )
        result = train_patient_models(pd.DataFrame(rows))
        self.assertLess(result.dengue_train_through, result.dengue_test_from)
        self.assertLess(
            result.hospitalization_train_through,
            result.hospitalization_test_from,
        )
        self.assertIn('roc_auc', result.dengue_metrics)
        self.assertIn('brier_score', result.hospitalization_metrics)


if __name__ == '__main__':
    unittest.main()
