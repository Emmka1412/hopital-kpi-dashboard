"""Prévision mensuelle simple et expliquée : saisonnier naïf, corrigé de la croissance annuelle.

Avec 24 mois d'historique, un modèle saisonnier complet (Holt-Winters, SARIMA) n'est pas fiable :
il faut au moins deux cycles complets pour estimer la saisonnalité et la tendance. On compare donc
deux méthodes que l'on sait expliquer, sur un backtest à origine glissante.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def naive(y: pd.Series, horizon: int = 3) -> pd.Series:
    """Répète la dernière valeur observée."""
    idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return pd.Series(np.repeat(float(y.iloc[-1]), horizon), index=idx)


def seasonal_naive(y: pd.Series, horizon: int = 3, growth: bool = False) -> pd.Series:
    """Reprend les mêmes mois de l'année précédente, avec en option la croissance des 12 derniers mois."""
    if len(y) < 12 or horizon > 12:
        raise ValueError("il faut au moins 12 mois d'historique et un horizon <= 12")
    g = 1.0
    if growth and len(y) >= 24:
        g = y.iloc[-12:].sum() / y.iloc[-24:-12].sum()
    idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return pd.Series(y.iloc[-12:].to_numpy()[:horizon] * g, index=idx)


def backtest(y: pd.Series, horizon: int = 3, min_train: int = 15) -> pd.DataFrame:
    """Erreur absolue moyenne (MAE) des deux méthodes, en rejouant le passé à origine glissante."""
    rows = []
    for end in range(min_train, len(y) - horizon + 1):
        train, actual = y.iloc[:end], y.iloc[end : end + horizon].to_numpy()
        rows.append(
            {
                "origine": y.index[end - 1],
                "mae_naif": float(np.mean(np.abs(naive(train, horizon).to_numpy() - actual))),
                "mae_saisonnier": float(np.mean(np.abs(seasonal_naive(train, horizon).to_numpy() - actual))),
            }
        )
    return pd.DataFrame(rows)
