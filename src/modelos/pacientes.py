from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = (
    'IDADE_ANOS',
    'CS_SEXO',
    'CS_GESTANT',
    'FEBRE',
    'MIALGIA',
    'CEFALEIA',
    'EXANTEMA',
    'VOMITO',
    'NAUSEA',
    'DOR_COSTAS',
    'CONJUNTVIT',
    'ARTRITE',
    'ARTRALGIA',
    'PETEQUIA_N',
    'DOR_RETRO',
    'DIABETES',
    'HEMATOLOG',
    'HEPATOPAT',
    'RENAL',
    'HIPERTENSA',
    'ACIDO_PEPT',
    'AUTO_IMUNE',
)
NUMERIC_FEATURES = ('IDADE_ANOS',)
DENGUE_POSITIVE_LABELS = {
    'dengue',
    'dengue_com_sinais_de_alarme',
    'dengue_grave',
}
DENGUE_NEGATIVE_LABELS = {
    'descartado',
    'chikungunya',
}


@dataclass
class PatientModelResult:
    dengue_model: Pipeline
    hospitalization_model: Pipeline
    dengue_metrics: dict[str, float]
    hospitalization_metrics: dict[str, float]
    dengue_train_through: pd.Timestamp
    dengue_test_from: pd.Timestamp
    hospitalization_train_through: pd.Timestamp
    hospitalization_test_from: pd.Timestamp


def _build_classifier() -> Pipeline:
    numeric = Pipeline(
        [
            ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
            ('scale', StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            (
                'imputer',
                SimpleImputer(
                    strategy='constant',
                    fill_value='__IGNORADO__',
                    keep_empty_features=True,
                ),
            ),
            ('onehot', OneHotEncoder(handle_unknown='ignore')),
        ]
    )
    preprocessor = ColumnTransformer(
        [
            ('numeric', numeric, list(NUMERIC_FEATURES)),
            (
                'categorical',
                categorical,
                [column for column in FEATURE_COLUMNS if column not in NUMERIC_FEATURES],
            ),
        ]
    )
    return Pipeline(
        [
            ('preprocess', preprocessor),
            (
                'classifier',
                LogisticRegression(
                    max_iter=500,
                    solver='lbfgs',
                    random_state=42,
                ),
            ),
        ]
    )


def _labels(df: pd.DataFrame) -> pd.Series:
    if 'CLASSI_FIN' not in df:
        raise ValueError('Coluna obrigatória ausente: CLASSI_FIN.')
    values = df['CLASSI_FIN'].astype('string').str.lower()
    raw_numeric = pd.to_numeric(values, errors='coerce')
    labels = pd.Series(pd.NA, index=df.index, dtype='Int64')
    labels.loc[
        values.isin(DENGUE_POSITIVE_LABELS) | raw_numeric.isin([10, 11, 12])
    ] = 1
    labels.loc[
        values.isin(DENGUE_NEGATIVE_LABELS) | raw_numeric.isin([5, 13])
    ] = 0
    return labels


def _age_in_years(age: pd.Series) -> pd.Series:
    values = pd.to_numeric(age, errors='coerce')
    result = pd.Series(np.nan, index=age.index, dtype='float64')
    years = values.ge(4000)
    months = values.ge(3000) & values.lt(4000)
    days = values.ge(2000) & values.lt(3000)
    result.loc[years] = values.loc[years] - 4000
    result.loc[months] = (values.loc[months] - 3000) / 12
    result.loc[days] = (values.loc[days] - 2000) / 365
    return result


def prepare_patient_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    for column in FEATURE_COLUMNS:
        if column in df.columns:
            features[column] = df[column]
    if 'IDADE_ANOS' not in features.columns and 'NU_IDADE_N' in df.columns:
        features['IDADE_ANOS'] = _age_in_years(df['NU_IDADE_N'])
    if 'IDADE_ANOS' in features.columns:
        age = pd.to_numeric(features['IDADE_ANOS'], errors='coerce')
        features['IDADE_ANOS'] = age.where(age.between(0, 120))
    for column in FEATURE_COLUMNS:
        if column not in features.columns:
            features[column] = np.nan
        if column not in NUMERIC_FEATURES:
            features[column] = features[column].astype('string').to_numpy(
                dtype=object,
                na_value=np.nan,
            )

    available = [column for column in FEATURE_COLUMNS if column in features]
    required_symptoms = {'FEBRE', 'MIALGIA', 'CEFALEIA'}
    if not required_symptoms.issubset(available):
        missing = sorted(required_symptoms.difference(available))
        raise ValueError(f'Colunas de sintomas ausentes para treino: {missing}')
    return features[available].copy()


def _time_split(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    test_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Timestamp, pd.Timestamp]:
    if not 0 < test_fraction < 1:
        raise ValueError('test_fraction deve ser maior que zero e menor que um.')
    valid = (
        dates.notna()
        & y.notna()
        & dates.le(pd.Timestamp.today().normalize())
    )
    X, y, dates = X.loc[valid], y.loc[valid].astype('int64'), dates.loc[valid]
    unique_dates = np.sort(dates.unique())
    if len(unique_dates) < 2:
        raise ValueError('São necessárias pelo menos duas datas para validação temporal.')
    split_index = max(1, min(len(unique_dates) - 1, int(len(unique_dates) * (1 - test_fraction))))
    cutoff = pd.Timestamp(unique_dates[split_index])
    train_mask = dates < cutoff
    test_mask = ~train_mask
    if y.loc[train_mask].nunique() < 2 or y.loc[test_mask].nunique() < 2:
        raise ValueError('O corte temporal não contém as duas classes em treino e teste.')
    return (
        X.loc[train_mask],
        X.loc[test_mask],
        y.loc[train_mask],
        y.loc[test_mask],
        dates.loc[train_mask].max(),
        dates.loc[test_mask].min(),
    )


def _fit_and_measure(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    test_fraction: float,
) -> tuple[Pipeline, dict[str, float], pd.Timestamp, pd.Timestamp]:
    X_train, X_test, y_train, y_test, train_through, test_from = _time_split(
        X, y, dates, test_fraction
    )
    model = _build_classifier()
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]
    metrics = {
        'roc_auc': float(roc_auc_score(y_test, probabilities)),
        'average_precision': float(average_precision_score(y_test, probabilities)),
        'brier_score': float(brier_score_loss(y_test, probabilities)),
        'test_rows': int(len(y_test)),
        'test_positive_rate': float(y_test.mean()),
    }
    return model, metrics, train_through, test_from


def train_patient_models(
    df: pd.DataFrame,
    test_fraction: float = 0.2,
) -> PatientModelResult:
    """Treina diagnóstico e proxy de hospitalização com corte temporal.

    Os modelos são experimentais: as notificações do SINAN não representam
    necessariamente todos os pacientes avaliados e não substituem avaliação clínica.
    """
    if 'DT_NOTIFIC' not in df:
        raise ValueError('Coluna obrigatória ausente: DT_NOTIFIC.')
    if 'HOSPITALIZ' not in df:
        raise ValueError('Coluna obrigatória ausente: HOSPITALIZ.')

    dates = pd.to_datetime(df['DT_NOTIFIC'], errors='coerce')
    X = prepare_patient_features(df)
    diagnosis = _labels(df)
    dengue, dengue_metrics, dengue_train_end, dengue_test_start = _fit_and_measure(
        X,
        diagnosis,
        dates,
        test_fraction,
    )

    class_labels = df['CLASSI_FIN'].astype('string').str.lower()
    confirmed_dengue = class_labels.isin({'dengue', 'dengue_classico'}) | pd.to_numeric(
        class_labels, errors='coerce'
    ).isin([1, 10])
    hospitalization = pd.to_numeric(df['HOSPITALIZ'], errors='coerce')
    known_hospitalization = hospitalization.isin([1, 2])
    severity_mask = confirmed_dengue & known_hospitalization
    severity_target = hospitalization.loc[severity_mask].eq(1).astype('int64')
    severity_model, severity_metrics, severity_train_end, severity_test_start = (
        _fit_and_measure(
            X.loc[severity_mask],
            severity_target,
            dates.loc[severity_mask],
            test_fraction,
        )
    )
    return PatientModelResult(
        dengue_model=dengue,
        hospitalization_model=severity_model,
        dengue_metrics=dengue_metrics,
        hospitalization_metrics=severity_metrics,
        dengue_train_through=dengue_train_end,
        dengue_test_from=dengue_test_start,
        hospitalization_train_through=severity_train_end,
        hospitalization_test_from=severity_test_start,
    )


def predict_patient(
    result: PatientModelResult,
    patient: pd.DataFrame,
) -> pd.DataFrame:
    """Retorna escores experimentais, não diagnóstico ou orientação clínica."""
    features = prepare_patient_features(patient)
    dengue_probability = result.dengue_model.predict_proba(features)[:, 1]
    hospitalization_probability = result.hospitalization_model.predict_proba(features)[:, 1]
    return pd.DataFrame(
        {
            'PROBABILIDADE_DENGUE_MODELO': dengue_probability,
            'SCORE_HOSPITALIZACAO_SE_DENGUE': hospitalization_probability,
        },
        index=patient.index,
    )
