import pandas as pd
import pytest

from hkpi import generate, pipeline


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    base = tmp_path_factory.mktemp("run")
    generate.main(["--out", str(base / "raw"), "--start", "2024-01-01", "--end", "2024-06-30", "--scale", "0.15", "--seed", "7"])
    result = pipeline.run(base / "raw", base / "processed", base / "reports")
    result["_base"] = base
    return result


def test_outputs_are_written(tables):
    base = tables["_base"]
    for name in ["dim_service", "dim_date", "fact_admission", "fact_consultation", "kpi_monthly_service"]:
        assert (base / "processed" / f"{name}.csv").exists()
    assert (base / "reports" / "quality_report.md").exists()


def test_primary_keys_unique_and_foreign_keys_valid(tables):
    assert tables["fact_admission"]["adm_id"].is_unique
    assert tables["fact_consultation"]["rdv_id"].is_unique
    codes = set(tables["dim_service"]["code_service"])
    assert set(tables["fact_admission"]["service_code"]) <= codes
    assert set(tables["fact_consultation"]["service_code"]) <= codes
    assert set(tables["fact_admission"]["date_entree"]) <= set(tables["dim_date"]["date"])


def test_no_negative_stay_and_valid_ages(tables):
    adm = tables["fact_admission"]
    assert (adm["duree_sejour_j"].dropna() >= 0).all()
    assert adm["age"].dropna().between(0, 110).all()


def test_kpi_values_are_in_plausible_ranges(tables):
    kpi = tables["kpi_monthly_service"]
    assert kpi["taux_occupation"].dropna().between(0, 1).all()
    assert kpi["taux_absence"].dropna().between(0, 1).all()
    assert kpi["dms_jours"].dropna().between(0, 15).all()
    assert (kpi["nb_admissions"] >= 0).all()


def test_kpi_totals_match_facts(tables):
    kpi, adm, cons = tables["kpi_monthly_service"], tables["fact_admission"], tables["fact_consultation"]
    assert kpi["nb_admissions"].sum() == len(adm)
    assert kpi["nb_rdv"].sum() == len(cons)


def test_quality_report_lists_sources(tables):
    report = (tables["_base"] / "reports" / "quality_report.md").read_text(encoding="utf-8")
    assert "admissions" in report and "consultations" in report


def test_pipeline_is_reproducible(tmp_path):
    for name in ("a", "b"):
        generate.main(["--out", str(tmp_path / name / "raw"), "--end", "2024-02-29", "--scale", "0.1", "--seed", "3"])
        pipeline.run(tmp_path / name / "raw", tmp_path / name / "out", tmp_path / name / "rep")
    a = pd.read_csv(tmp_path / "a" / "out" / "kpi_monthly_service.csv")
    b = pd.read_csv(tmp_path / "b" / "out" / "kpi_monthly_service.csv")
    pd.testing.assert_frame_equal(a, b)
