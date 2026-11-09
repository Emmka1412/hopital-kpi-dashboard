"""Modélisation en étoile : dimensions, faits et table de KPI mensuels prête pour Power BI."""

from __future__ import annotations

import numpy as np
import pandas as pd

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def build_dim_service(services: pd.DataFrame) -> pd.DataFrame:
    return services[["code_service", "libelle", "pole", "lits"]].sort_values("code_service").reset_index(drop=True)


def build_dim_date(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start.normalize(), end.normalize(), freq="D")})
    d["annee"] = d["date"].dt.year
    d["trimestre"] = d["date"].dt.quarter
    d["mois"] = d["date"].dt.month
    d["mois_libelle"] = d["mois"].map(lambda m: MONTHS_FR[m - 1])
    d["mois_debut"] = d["date"].dt.to_period("M").dt.to_timestamp()
    d["annee_mois"] = d["date"].dt.strftime("%Y-%m")
    d["jour_semaine_num"] = d["date"].dt.dayofweek + 1
    d["jour_semaine"] = d["jour_semaine_num"].map(lambda n: DAYS_FR[n - 1])
    d["est_weekend"] = d["jour_semaine_num"] >= 6
    return d


def build_fact_admission(adm: pd.DataFrame) -> pd.DataFrame:
    f = adm.copy()
    bins = [-1, 17, 39, 59, 74, 200]
    labels = ["0-17", "18-39", "40-59", "60-74", "75+"]
    f["tranche_age"] = pd.cut(f["age"], bins=bins, labels=labels).astype("string").fillna("Non renseigné")
    return f


def build_fact_consultation(cons: pd.DataFrame) -> pd.DataFrame:
    return cons.copy()


def _bed_days(adm: pd.DataFrame, period_end: pd.Timestamp) -> pd.DataFrame:
    """Jours-lits occupés par service et par mois (un séjour d'un jour compte pour 1 jour-lit)."""
    done = adm.dropna(subset=["date_sortie"])
    nights = (done["date_sortie"] - done["date_entree"]).dt.days.clip(lower=1).to_numpy()
    idx = np.repeat(np.arange(len(done)), nights)
    offsets = np.arange(nights.sum()) - np.repeat(np.cumsum(nights) - nights, nights)
    days = done["date_entree"].to_numpy()[idx] + offsets.astype("timedelta64[D]")
    out = pd.DataFrame({"service_code": done["service_code"].to_numpy()[idx], "jour": pd.to_datetime(days)})
    out = out[out["jour"] <= period_end]
    out["mois_debut"] = out["jour"].dt.to_period("M").dt.to_timestamp()
    return out.groupby(["mois_debut", "service_code"]).size().rename("jours_lit_occupes").reset_index()


def build_kpi_monthly(adm: pd.DataFrame, cons: pd.DataFrame, dim_service: pd.DataFrame) -> pd.DataFrame:
    adm = adm.copy()
    cons = cons.copy()
    adm["mois_debut"] = adm["date_entree"].dt.to_period("M").dt.to_timestamp()
    cons["mois_debut"] = cons["date_rdv"].dt.to_period("M").dt.to_timestamp()
    first = min(adm["mois_debut"].min(), cons["mois_debut"].min())
    last = max(adm["mois_debut"].max(), cons["mois_debut"].max())
    months = pd.date_range(first, last, freq="MS")

    grid = pd.MultiIndex.from_product([months, dim_service["code_service"]], names=["mois_debut", "service_code"]).to_frame(index=False)

    a = (
        adm.groupby(["mois_debut", "service_code"])
        .agg(
            nb_admissions=("adm_id", "size"),
            nb_sejours_termines=("date_sortie", "count"),
            dms_jours=("duree_sejour_j", "mean"),
            nb_entrees_urgences=("mode_entree", lambda s: int((s == "Urgences").sum())),
            nb_deces=("mode_sortie", lambda s: int((s == "Décès").sum())),
        )
        .reset_index()
    )
    c = (
        cons.groupby(["mois_debut", "service_code"])
        .agg(
            nb_rdv=("rdv_id", "size"),
            nb_honores=("statut", lambda s: int((s == "Honoré").sum())),
            nb_absents=("statut", lambda s: int((s == "Absent").sum())),
            nb_annules=("statut", lambda s: int((s == "Annulé").sum())),
            duree_moyenne_rdv_min=("duree_min", "mean"),
        )
        .reset_index()
    )
    beds = _bed_days(adm, adm["date_entree"].max())

    k = grid.merge(a, how="left", on=["mois_debut", "service_code"])
    k = k.merge(c, how="left", on=["mois_debut", "service_code"])
    k = k.merge(beds, how="left", on=["mois_debut", "service_code"])
    count_cols = ["nb_admissions", "nb_sejours_termines", "nb_entrees_urgences", "nb_deces", "nb_rdv", "nb_honores", "nb_absents", "nb_annules"]
    k[count_cols] = k[count_cols].fillna(0).astype(int)

    lits = k["service_code"].map(dim_service.set_index("code_service")["lits"])
    has_beds = lits > 0
    first_month = k["mois_debut"] == first  # démarrage à vide : séjours antérieurs non exportés
    computable = has_beds & ~first_month
    k["jours_lit_disponibles"] = (lits * k["mois_debut"].dt.days_in_month).where(computable)
    k["jours_lit_occupes"] = k["jours_lit_occupes"].fillna(0).where(computable)
    k["taux_occupation"] = (k["jours_lit_occupes"] / k["jours_lit_disponibles"]).clip(upper=1).round(4)
    k["part_entrees_urgences"] = (k["nb_entrees_urgences"] / k["nb_admissions"].where(k["nb_admissions"] > 0)).round(4)
    k["taux_absence"] = (k["nb_absents"] / k["nb_rdv"].where(k["nb_rdv"] > 0)).round(4)
    k["dms_jours"] = k["dms_jours"].round(2)
    k["duree_moyenne_rdv_min"] = k["duree_moyenne_rdv_min"].round(1)
    return k
