"""Analyse des KPI : tendance, saisonnalité, pression sur les services, prévision à 3 mois.

Produit deux fichiers à partir des tables du modèle en étoile :

* ``data/processed/forecast_admissions.csv`` : historique + prévision (pour Power BI et PostgreSQL) ;
* ``reports/analyse.md`` : une lecture interprétée des résultats, tous les chiffres étant calculés.

Les données sont synthétiques : la saisonnalité retrouvée est celle que le générateur a codée.
Ce rapport valide la méthode, pas un phénomène hospitalier réel.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .forecast import backtest, seasonal_naive
from .model import MONTHS_FR

SEUIL_TENSION = 0.80  # mêmes seuils que la mesure DAX « Alerte occupation »
SEUIL_SATURATION = 0.90


def fr(value: float, digits: int = 1) -> str:
    """Nombre au format français : virgule décimale, espace pour les milliers."""
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def monthly_admissions(kpi: pd.DataFrame) -> pd.Series:
    return kpi.groupby("mois_debut")["nb_admissions"].sum().sort_index()


def seasonal_index(y: pd.Series) -> pd.Series:
    """Indice par mois civil : moyenne du mois / moyenne générale (1,00 = mois moyen)."""
    by_month = y.groupby(y.index.month).mean()
    return (by_month / y.mean()).rename("indice_saisonnier")


def year_over_year(y: pd.Series) -> float:
    """Évolution des 12 derniers mois par rapport aux 12 mois précédents (0,02 = +2 %)."""
    if len(y) < 24:
        raise ValueError("il faut au moins 24 mois pour comparer deux années")
    return float(y.iloc[-12:].sum() / y.iloc[-24:-12].sum() - 1)


def trend_pct_per_year(y: pd.Series) -> float:
    """Pente de la série désaisonnalisée, en % du niveau moyen par an (régression linéaire)."""
    index = seasonal_index(y)
    adjusted = y / index.reindex(y.index.month).to_numpy()
    slope = np.polyfit(np.arange(len(adjusted)), adjusted.to_numpy(), 1)[0]
    return float(12 * slope / adjusted.mean() * 100)


def occupancy_by_service(kpi: pd.DataFrame, services: pd.DataFrame) -> pd.DataFrame:
    """Occupation par service : rapport de sommes (jamais une moyenne de taux)."""
    k = kpi.dropna(subset=["jours_lit_disponibles"])
    k = k[k["jours_lit_disponibles"] > 0]
    g = k.groupby("service_code")[["jours_lit_occupes", "jours_lit_disponibles"]].sum()
    g["occupation"] = g["jours_lit_occupes"] / g["jours_lit_disponibles"]
    out = g.join(services.set_index("code_service")["libelle"]).reset_index()
    return out.sort_values("occupation", ascending=False)[["libelle", "occupation"]].reset_index(drop=True)


def absence_by_service(kpi: pd.DataFrame, services: pd.DataFrame) -> pd.DataFrame:
    g = kpi[kpi["nb_rdv"] > 0].groupby("service_code")[["nb_absents", "nb_rdv"]].sum()
    g["taux_absence"] = g["nb_absents"] / g["nb_rdv"]
    out = g.join(services.set_index("code_service")["libelle"]).reset_index()
    return out.sort_values("taux_absence", ascending=False)[["libelle", "taux_absence"]].reset_index(drop=True)


def forecast_table(y: pd.Series, horizon: int = 3) -> pd.DataFrame:
    fc = seasonal_naive(y, horizon, growth=True)
    return pd.concat(
        [
            pd.DataFrame({"mois_debut": y.index, "admissions": y.to_numpy(), "type": "historique"}),
            pd.DataFrame({"mois_debut": fc.index, "admissions": fc.round(0).to_numpy(), "type": "prévision"}),
        ],
        ignore_index=True,
    )


def build_report(kpi: pd.DataFrame, services: pd.DataFrame, horizon: int = 3) -> str:
    y = monthly_admissions(kpi)
    idx = seasonal_index(y)
    peak, trough = int(idx.idxmax()), int(idx.idxmin())
    yoy = year_over_year(y)
    trend = trend_pct_per_year(y)
    occ = occupancy_by_service(kpi, services)
    absence = absence_by_service(kpi, services)
    absence_global = kpi["nb_absents"].sum() / kpi["nb_rdv"].sum()
    bt = backtest(y, horizon)
    mae_n, mae_s = bt["mae_naif"].mean(), bt["mae_saisonnier"].mean()
    fc = seasonal_naive(y, horizon, growth=True)
    first, last = y.index[0], y.index[-1]

    lines = [
        "# Analyse des KPI : tendance, saisonnalité et prévision",
        "",
        f"Généré par `python -m hkpi.analysis` sur {len(y)} mois ({first:%m/%Y} à {last:%m/%Y}). "
        "Données synthétiques : la saisonnalité décrite ci-dessous est celle codée dans le générateur ; "
        "ce rapport valide la méthode, pas un phénomène hospitalier réel.",
        "",
        "## 1. Lecture en cinq points",
        "",
        f"1. **Volume et tendance.** Les 12 derniers mois comptent {fr(100 * yoy)} % d'admissions "
        f"{'de plus' if yoy >= 0 else 'de moins'} que les 12 précédents. Une fois la saisonnalité retirée, "
        f"la tendance est de {fr(trend)} % par an : "
        + ("l'activité est stable" if abs(trend) < 2 else "la tendance est nette")
        + " sur la période.",
        f"2. **Saisonnalité.** Le pic est en {MONTHS_FR[peak - 1]} (indice {fr(idx[peak], 2)}) et le creux en "
        f"{MONTHS_FR[trough - 1]} (indice {fr(idx[trough], 2)}) : l'activité du mois le plus chargé est "
        f"{fr(idx[peak] / idx[trough], 2)} fois celle du mois le plus calme.",
        f"3. **Pression sur les lits.** {occ.iloc[0]['libelle']} a l'occupation la plus élevée "
        f"({fr(100 * occ.iloc[0]['occupation'])} %), "
        + (
            f"au-dessus du seuil de tension de {fr(100 * SEUIL_TENSION, 0)} %. "
            if occ.iloc[0]["occupation"] >= SEUIL_TENSION
            else f"sous le seuil de tension de {fr(100 * SEUIL_TENSION, 0)} %. "
        )
        + "Les séjours d'un jour comptent pour 1 jour-lit, ce qui gonfle l'occupation des services à séjours très courts.",
        f"4. **Consultations.** Le taux d'absence global est de {fr(100 * absence_global)} %, "
        f"de {fr(100 * absence['taux_absence'].min())} % ({absence.iloc[-1]['libelle']}) à "
        f"{fr(100 * absence['taux_absence'].max())} % ({absence.iloc[0]['libelle']}) selon les services.",
        f"5. **Prévision.** Pour les {horizon} prochains mois, la méthode saisonnière prévoit "
        + ", ".join(f"{fr(v, 0)} ({d:%m/%Y})" for d, v in fc.items())
        + f" admissions, avec une erreur attendue d'environ ± {fr(mae_s, 0)} admissions par mois.",
        "",
        "## 2. Indice saisonnier par mois civil",
        "",
        "| Mois | Indice (1,00 = mois moyen) |",
        "|---|---:|",
        *[f"| {MONTHS_FR[m - 1]} | {fr(v, 3)} |" for m, v in idx.items()],
        "",
        "## 3. Occupation par service",
        "",
        "| Service | Taux d'occupation | Lecture |",
        "|---|---:|---|",
        *[
            f"| {r.libelle} | {fr(100 * r.occupation)} % | "
            + ("saturation" if r.occupation >= SEUIL_SATURATION else "tension" if r.occupation >= SEUIL_TENSION else "normal")
            + " |"
            for r in occ.itertuples()
        ],
        "",
        "## 4. Prévision : méthode et validation",
        "",
        "Avec 24 mois d'historique, un modèle saisonnier complet (Holt-Winters, SARIMA) n'est pas fiable : "
        "il faut au moins deux cycles complets pour séparer la tendance de la saisonnalité et en valider "
        "l'estimation. On compare donc deux méthodes expliquables en une phrase, par un backtest à origine glissante "
        f"({len(bt)} origines, horizon {horizon} mois).",
        "",
        "| Méthode | Erreur absolue moyenne (admissions/mois) | En % du niveau moyen |",
        "|---|---:|---:|",
        f"| Naïve (répète le dernier mois) | {fr(mae_n)} | {fr(100 * mae_n / y.mean())} % |",
        f"| Saisonnière naïve (mêmes mois de l'an passé) | {fr(mae_s)} | {fr(100 * mae_s / y.mean())} % |",
        "",
        "La prévision publiée applique en plus la croissance des 12 derniers mois "
        f"({fr(100 * yoy)} %) aux mêmes mois de l'année précédente.",
        "",
        "## 5. Limites",
        "",
        "- Données synthétiques : la saisonnalité vient du générateur, donc la validation prouve le code et la méthode.",
        "- Deux années seulement : l'indice saisonnier est estimé sur les mêmes données que celles qu'il sert à désaisonnaliser.",
        "- La prévision ne tient pas compte d'événements exceptionnels (épidémie, fermeture de service).",
        "- Premier mois sans taux d'occupation, séjours sans date de sortie exclus des durées : voir le rapport qualité.",
        "",
    ]
    return "\n".join(lines)


def run(processed: str | Path = "data/processed", reports: str | Path = "reports", horizon: int = 3) -> pd.DataFrame:
    processed, reports = Path(processed), Path(reports)
    kpi = pd.read_csv(processed / "kpi_monthly_service.csv", parse_dates=["mois_debut"])
    services = pd.read_csv(processed / "dim_service.csv")
    table = forecast_table(monthly_admissions(kpi), horizon)
    table.to_csv(processed / "forecast_admissions.csv", index=False, date_format="%Y-%m-%d")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "analyse.md").write_text(build_report(kpi, services, horizon), encoding="utf-8")
    return table


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--processed", default="data/processed")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--horizon", type=int, default=3)
    args = parser.parse_args(argv)
    table = run(args.processed, args.reports, args.horizon)
    print(f"Prévision écrite : {args.processed}/forecast_admissions.csv ({len(table)} lignes) · rapport : {args.reports}/analyse.md")


if __name__ == "__main__":
    main()
