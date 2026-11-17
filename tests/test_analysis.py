import re

import numpy as np
import pandas as pd
import pytest

from hkpi import analysis, generate, pipeline


def _series(n=24, amplitude=0.2, trend=0.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="MS")
    season = 1 + amplitude * np.cos(2 * np.pi * (idx.month - 1) / 12)  # pic en janvier
    return pd.Series(1000 * season * (1 + trend * np.arange(n) / 12), index=idx)


def test_seasonal_index_averages_to_one_and_finds_the_peak():
    idx = analysis.seasonal_index(_series())
    assert idx.mean() == pytest.approx(1.0)
    assert idx.idxmax() == 1  # janvier
    assert idx.idxmin() == 7  # juillet


def test_year_over_year_matches_known_growth():
    y = _series()
    y.iloc[-12:] = y.iloc[-12:] * 1.05
    assert analysis.year_over_year(y) == pytest.approx(0.05)


def test_year_over_year_needs_two_years():
    with pytest.raises(ValueError):
        analysis.year_over_year(_series(18))


def test_trend_is_zero_on_a_pure_seasonal_series_and_positive_with_growth():
    assert abs(analysis.trend_pct_per_year(_series())) < 1.0
    assert analysis.trend_pct_per_year(_series(trend=0.10)) > 5.0


def test_occupancy_is_a_ratio_of_sums_not_a_mean_of_rates():
    kpi = pd.DataFrame(
        {
            "service_code": ["A", "A", "B"],
            "jours_lit_occupes": [10.0, 10.0, 90.0],
            "jours_lit_disponibles": [100.0, 100.0, 100.0],
        }
    )
    services = pd.DataFrame({"code_service": ["A", "B"], "libelle": ["Service A", "Service B"]})
    occ = analysis.occupancy_by_service(kpi, services).set_index("libelle")["occupation"]
    assert occ["Service A"] == pytest.approx(0.10)
    assert occ["Service B"] == pytest.approx(0.90)


def test_fr_formats_numbers_the_french_way():
    assert analysis.fr(1442.0, 0) == "1 442"
    assert analysis.fr(10.14, 1) == "10,1"


@pytest.fixture(scope="module")
def processed(tmp_path_factory):
    base = tmp_path_factory.mktemp("analysis")
    generate.main(["--out", str(base / "raw"), "--scale", "0.1", "--seed", "5"])
    pipeline.run(base / "raw", base / "processed", base / "reports")
    analysis.run(base / "processed", base / "reports")
    return base


def test_run_writes_forecast_and_report(processed):
    fc = pd.read_csv(processed / "processed" / "forecast_admissions.csv", parse_dates=["mois_debut"])
    assert set(fc["type"]) == {"historique", "prévision"}
    assert (fc.loc[fc["type"] == "prévision", "mois_debut"].min() > fc.loc[fc["type"] == "historique", "mois_debut"].max())
    assert (fc["admissions"] > 0).all()
    assert fc["mois_debut"].is_unique


def test_report_has_all_sections_and_no_missing_values(processed):
    text = (processed / "reports" / "analyse.md").read_text(encoding="utf-8")
    for heading in ["## 1. Lecture en cinq points", "## 2. Indice saisonnier", "## 3. Occupation", "## 4. Prévision", "## 5. Limites"]:
        assert heading in text
    assert not re.search(r"\b(nan|inf)\b", text.lower())
