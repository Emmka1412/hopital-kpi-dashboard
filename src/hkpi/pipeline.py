"""Pipeline de bout en bout : sources brutes -> nettoyage -> modèle en étoile -> CSV pour Power BI."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from .clean import QualityLog, clean_admissions, clean_consultations, clean_services
from .model import build_dim_date, build_dim_service, build_fact_admission, build_fact_consultation, build_kpi_monthly
from .quality import write_reports

log = logging.getLogger("hkpi")


def load_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    admissions = pd.read_csv(raw_dir / "admissions.csv", sep=";", dtype=str, keep_default_na=False, na_values=[""])
    services = pd.read_excel(raw_dir / "services.xlsx", header=2)  # titre + ligne vide au-dessus de l'en-tête
    with open(raw_dir / "consultations.json", encoding="utf-8") as fh:
        payload = json.load(fh)
    consultations = pd.json_normalize(payload["rendez_vous"])
    return {"admissions": admissions, "services": services, "consultations": consultations}


def check_integrity(dim_service: pd.DataFrame, dim_date: pd.DataFrame, fact_adm: pd.DataFrame, fact_cons: pd.DataFrame) -> None:
    """Contrôles bloquants : clés primaires uniques, clés étrangères valides."""
    problems = []
    if dim_service["code_service"].duplicated().any():
        problems.append("dim_service : code_service en double")
    if fact_adm["adm_id"].duplicated().any():
        problems.append("fact_admission : adm_id en double")
    if fact_cons["rdv_id"].duplicated().any():
        problems.append("fact_consultation : rdv_id en double")
    codes = set(dim_service["code_service"])
    if not set(fact_adm["service_code"]) <= codes:
        problems.append("fact_admission : service_code absent de dim_service")
    if not set(fact_cons["service_code"]) <= codes:
        problems.append("fact_consultation : service_code absent de dim_service")
    dates = set(dim_date["date"])
    if not set(fact_adm["date_entree"]) <= dates or not set(fact_cons["date_rdv"]) <= dates:
        problems.append("faits : dates hors dim_date")
    if problems:
        raise ValueError("Contrôles d'intégrité en échec : " + " ; ".join(problems))


def run(raw_dir: str | Path, out_dir: str | Path, reports_dir: str | Path) -> dict[str, pd.DataFrame]:
    raw_dir, out_dir, reports_dir = Path(raw_dir), Path(out_dir), Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    qlog = QualityLog()

    raw = load_raw(raw_dir)
    services = clean_services(raw["services"], qlog)
    valid_codes = services["code_service"].tolist()
    adm, rej_adm = clean_admissions(raw["admissions"], valid_codes, qlog)
    cons, rej_cons = clean_consultations(raw["consultations"], valid_codes, qlog)

    dim_service = build_dim_service(services)
    fact_adm = build_fact_admission(adm)
    fact_cons = build_fact_consultation(cons)
    all_dates = pd.concat([fact_adm["date_entree"], fact_adm["date_sortie"].dropna(), fact_cons["date_rdv"]])
    dim_date = build_dim_date(all_dates.min(), all_dates.max())
    check_integrity(dim_service, dim_date, fact_adm, fact_cons)
    kpi = build_kpi_monthly(fact_adm, fact_cons, dim_service)

    tables = {
        "dim_service": dim_service,
        "dim_date": dim_date,
        "fact_admission": fact_adm,
        "fact_consultation": fact_cons,
        "kpi_monthly_service": kpi,
    }
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        log.info("%s : %d lignes", name, len(df))
    write_reports(qlog, {"admissions": rej_adm, "consultations": rej_cons}, reports_dir)
    return tables


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--out", default="data/processed")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.raw, args.out, args.reports)
    log.info("Terminé. Tables dans %s, rapport qualité dans %s/quality_report.md", args.out, args.reports)


if __name__ == "__main__":
    main()
