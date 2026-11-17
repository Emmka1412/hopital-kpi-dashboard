import pandas as pd
import pytest

from hkpi.forecast import backtest, naive, seasonal_naive


def _series(n=24):
    idx = pd.date_range("2024-01-01", periods=n, freq="MS")
    return pd.Series([100 + 10 * (i % 12) for i in range(n)], index=idx, dtype=float)


def test_seasonal_naive_repeats_same_months_last_year():
    y = _series()
    f = seasonal_naive(y, 3)
    assert f.index[0] == pd.Timestamp("2026-01-01")
    assert f.tolist() == y.iloc[-12:-9].tolist()


def test_seasonal_naive_beats_naive_on_a_seasonal_series():
    bt = backtest(_series())
    assert bt["mae_saisonnier"].mean() < bt["mae_naif"].mean()


def test_growth_correction_scales_forecast():
    y = _series()
    y.iloc[-12:] = y.iloc[-12:] * 1.1  # +10 % sur la dernière année
    assert seasonal_naive(y, 3, growth=True).iloc[0] == pytest.approx(y.iloc[-12] * 1.1)


def test_needs_a_full_year():
    with pytest.raises(ValueError):
        seasonal_naive(_series(8), 3)
