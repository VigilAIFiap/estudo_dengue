from __future__ import annotations

import numpy as np
import pandas as pd


DENGUE_LABELS = {
    'dengue',
    'dengue_com_sinais_de_alarme',
    'dengue_grave',
}


def _confirmed_dengue_mask(df: pd.DataFrame) -> pd.Series:
    if 'CLASSI_FIN' not in df.columns:
        raise ValueError('A camada precisa conter CLASSI_FIN para contar casos confirmados.')
    labels = df['CLASSI_FIN'].astype('string').str.lower()
    numeric = pd.to_numeric(labels, errors='coerce')
    return labels.isin(DENGUE_LABELS) | numeric.isin([10, 11, 12])


def _prepare_daily_cases(
    df: pd.DataFrame,
    date_column: str,
    as_of: pd.Timestamp | None,
) -> pd.Series:
    if date_column not in df.columns:
        raise ValueError(f'Coluna de data ausente: {date_column}')

    dates = pd.to_datetime(df[date_column], errors='coerce')
    confirmed = _confirmed_dengue_mask(df)
    valid = dates.notna() & confirmed
    if as_of is not None:
        valid &= dates <= pd.Timestamp(as_of).normalize()
    if not valid.any():
        raise ValueError('Não há casos confirmados com datas válidas no período.')

    daily = (
        dates[valid]
        .dt.floor('D')
        .value_counts()
        .sort_index()
        .astype('int64')
    )
    return daily.asfreq('D', fill_value=0)


def prepare_monthly_cases(
    df: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
    min_months: int = 24,
) -> pd.Series:
    """Constrói série mensal de casos confirmados, descartando o mês parcial."""
    if min_months < 1:
        raise ValueError('min_months deve ser maior que zero.')
    daily = _prepare_daily_cases(df, 'DT_NOTIFIC', as_of)
    monthly = daily.resample('MS').sum()
    cutoff = pd.Timestamp(as_of or pd.Timestamp.today()).to_period('M').start_time
    monthly = monthly[monthly.index < cutoff]
    if len(monthly) < min_months:
        raise ValueError(
            f'São necessários pelo menos {min_months} meses completos; '
            f'a base tem {len(monthly)}.'
        )
    return monthly


def prepare_daily_cases(
    df: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
    max_age_days: int = 30,
    min_days: int = 180,
) -> pd.Series:
    """Constrói série diária pela data de início dos sintomas (DT_SIN_PRI)."""
    if max_age_days < 0 or min_days < 1:
        raise ValueError('max_age_days deve ser não negativo e min_days positivo.')
    daily = _prepare_daily_cases(df, 'DT_SIN_PRI', as_of)
    reference_date = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
    age = (reference_date - daily.index[-1].normalize()).days
    if age > max_age_days:
        raise ValueError(
            f'A série diária está desatualizada: último dia com dados '
            f'{daily.index[-1].date()} ({age} dias atrás; limite {max_age_days}).'
        )
    if len(daily) < min_days:
        raise ValueError(
            f'São necessários pelo menos {min_days} dias consecutivos; '
            f'a base tem {len(daily)}.'
        )
    return daily


def _forecast(series: pd.Series, steps: int, seasonal_period: int) -> pd.DataFrame:
    if steps < 1:
        raise ValueError('steps deve ser maior que zero.')
    if len(series) < 2 * seasonal_period:
        raise ValueError(
            f'São necessários pelo menos {2 * seasonal_period} observações '
            f'para sazonalidade {seasonal_period}.'
        )

    from pmdarima import auto_arima

    model = auto_arima(
        series.astype(float).to_numpy(),
        seasonal=True,
        m=seasonal_period,
        stepwise=True,
        suppress_warnings=True,
        error_action='raise',
        max_p=3,
        max_q=3,
        max_P=2,
        max_Q=2,
    )
    prediction, confidence = model.predict(
        n_periods=steps,
        return_conf_int=True,
        alpha=0.05,
    )
    index = pd.date_range(
        series.index[-1] + pd.tseries.frequencies.to_offset(series.index.freq),
        periods=steps,
        freq=series.index.freq,
    )
    return pd.DataFrame(
        {
            'PREVISAO': np.maximum(prediction, 0).round().astype('int64'),
            'LIMITE_INFERIOR_95': np.maximum(confidence[:, 0], 0),
            'LIMITE_SUPERIOR_95': np.maximum(confidence[:, 1], 0),
        },
        index=index,
    ).rename_axis('DATA')


def forecast_monthly_cases(series: pd.Series, months: int = 12) -> pd.DataFrame:
    """Prevê os próximos meses usando SARIMA sazonal anual."""
    if series.index.freqstr != 'MS':
        series = series.asfreq('MS', fill_value=0)
    return _forecast(series, steps=months, seasonal_period=12)


def forecast_next_30_days(series: pd.Series) -> pd.DataFrame:
    """Prevê os próximos 30 dias; rejeita séries ainda sem atualização recente."""
    if series.index.freqstr != 'D':
        series = series.asfreq('D', fill_value=0)
    return _forecast(series, steps=30, seasonal_period=7)


def rolling_backtest(
    series: pd.Series,
    horizon: int,
    seasonal_period: int,
    folds: int = 3,
) -> dict[str, float | bool]:
    """Compara SARIMA com baseline sazonal em janelas temporais futuras."""
    if horizon < 1 or seasonal_period < 1 or folds < 1:
        raise ValueError('horizon, seasonal_period e folds devem ser positivos.')
    initial_size = len(series) - horizon * folds
    if initial_size < 2 * seasonal_period:
        raise ValueError(
            'A série é curta demais para validação temporal com o horizonte e '
            'a sazonalidade selecionados.'
        )

    actual, predicted, baseline = [], [], []
    for fold in range(folds):
        end = initial_size + fold * horizon
        train = series.iloc[:end]
        test = series.iloc[end:end + horizon]
        forecast = _forecast(train, steps=len(test), seasonal_period=seasonal_period)
        actual.extend(test.astype(float).tolist())
        predicted.extend(forecast['PREVISAO'].astype(float).tolist())
        seasonal_values = train.iloc[-seasonal_period:].astype(float).to_numpy()
        baseline.extend(np.resize(seasonal_values, len(test)).tolist())

    actual_values = np.asarray(actual)
    predicted_values = np.asarray(predicted)
    baseline_values = np.asarray(baseline)
    model_mae = float(np.mean(np.abs(actual_values - predicted_values)))
    baseline_mae = float(np.mean(np.abs(actual_values - baseline_values)))
    return {
        'model_mae': model_mae,
        'seasonal_naive_mae': baseline_mae,
        'model_rmse': float(np.sqrt(np.mean((actual_values - predicted_values) ** 2))),
        'seasonal_naive_rmse': float(
            np.sqrt(np.mean((actual_values - baseline_values) ** 2))
        ),
        'beats_seasonal_naive': model_mae < baseline_mae,
        'test_observations': int(len(actual_values)),
    }
