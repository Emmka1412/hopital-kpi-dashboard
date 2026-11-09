"""Génère des sources brutes synthétiques, hétérogènes et volontairement imparfaites.

Aucune donnée réelle n'est utilisée : tout est tiré au sort avec une graine fixe, ce qui
rend le projet reproductible et sans enjeu de confidentialité. Trois sources de formats
différents imitent des exports de systèmes distincts :

* ``admissions.csv``      : système d'admission (CSV, séparateur « ; »)
* ``services.xlsx``       : référentiel administratif des services (Excel avec en-tête décalé)
* ``consultations.json``  : outil de prise de rendez-vous (JSON imbriqué)

Des anomalies réalistes sont injectées (doublons, formats de dates mixtes, libellés variables,
valeurs aberrantes, dates incohérentes...) pour que l'étape de nettoyage ait un vrai travail à faire.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook

# code, libellé officiel, pôle, lits, durée moyenne de séjour (jours), rendez-vous par jour ouvré
SERVICES = [
    ("URG", "Urgences", "Urgences et soins critiques", 20, 1.2, 0),
    ("CAR", "Cardiologie", "Médecine", 30, 5.0, 14),
    ("PED", "Pédiatrie", "Mère-enfant", 24, 3.5, 16),
    ("CHI", "Chirurgie", "Chirurgie", 36, 4.5, 12),
    ("MAT", "Maternité", "Mère-enfant", 28, 3.0, 10),
    ("MIN", "Médecine interne", "Médecine", 32, 7.0, 12),
    ("REA", "Réanimation", "Urgences et soins critiques", 12, 8.0, 0),
    ("RAD", "Radiologie", "Plateau technique", 0, 0.0, 30),
]

# Variantes de libellés, telles qu'on en trouve dans des exports hétérogènes (la première est la forme propre).
DIRTY_LABELS = {
    "URG": ["Urgences", "URGENCES", "urgences ", "Urg.", "Service des urgences"],
    "CAR": ["Cardiologie", "CARDIOLOGIE", "Cardio", "cardiologie "],
    "PED": ["Pédiatrie", "Pediatrie", "PEDIATRIE", "Péd."],
    "CHI": ["Chirurgie", "CHIRURGIE", "Chir.", "Chirurgie générale"],
    "MAT": ["Maternité", "Maternite", "MATERNITE", "Mat."],
    "MIN": ["Médecine interne", "Medecine interne", "MED INTERNE", "Méd. interne"],
    "REA": ["Réanimation", "Reanimation", "REA", "Réa."],
    "RAD": ["Radiologie", "RADIOLOGIE", "Radio", "Imagerie"],
}

ENTRY_VARIANTS = {
    "Urgences": ["Urgences", "URGENCES", "urgence"],
    "Programmée": ["Programmée", "programmée", "Prog.", "programme"],
    "Transfert": ["Transfert", "transfert"],
}
EXIT_VARIANTS = {
    "Domicile": ["Domicile", "domicile", "DOMICILE"],
    "Transfert": ["Transfert", "transfert"],
    "Décès": ["Décès", "deces", "DÉCÈS"],
    "Autre": ["Autre"],
}
SEX_VARIANTS = {"M": ["M", "M", "H", "Masculin", "homme"], "F": ["F", "F", "Féminin", "femme"]}
STATUS_VARIANTS = {
    "Honoré": ["Honoré", "honoré", "HONORE", "réalisé"],
    "Absent": ["Absent", "ABSENT", "no show"],
    "Annulé": ["Annulé", "annule", "ANNULÉ"],
}


def _choice(rng: np.random.Generator, options: list[str]) -> str:
    return options[int(rng.integers(0, len(options)))]


def _dirty_patient_id(num: int, rng: np.random.Generator) -> str:
    r = rng.random()
    if r < 0.80:
        return f"P{num:06d}"
    if r < 0.92:
        return f"p{num}"
    return str(num)


def _dirty_date(ts: pd.Timestamp, rng: np.random.Generator) -> str:
    r = rng.random()
    if r < 0.70:
        return ts.strftime("%d/%m/%Y")
    if r < 0.90:
        return ts.strftime("%Y-%m-%d")
    return ts.strftime("%d-%m-%Y")


def _simulate_stay(rng: np.random.Generator, code: str, day: pd.Timestamp, mean_los: float) -> dict:
    stay = int(round(rng.gamma(2.0, mean_los / 2.0)))
    if code == "PED":
        age, sex = int(rng.integers(0, 18)), _choice(rng, ["M", "F"])
    elif code == "MAT":
        age, sex = int(rng.integers(18, 43)), "F"
    else:
        mu = 68 if code in ("CAR", "REA", "MIN") else 52
        age, sex = int(np.clip(rng.normal(mu, 16), 18, 98)), _choice(rng, ["M", "F"])
    if code == "URG":
        entry = "Urgences"
    else:
        entry = str(rng.choice(["Programmée", "Urgences", "Transfert"], p=[0.55, 0.35, 0.10]))
    p_death = 0.15 if code == "REA" else 0.02
    exit_mode = str(
        rng.choice(["Domicile", "Transfert", "Décès", "Autre"], p=[0.90 - p_death, 0.08, p_death, 0.02])
    )
    return {
        "service": code,
        "patient": int(rng.integers(1, 12000)),
        "entree": day,
        "sortie": day + pd.Timedelta(days=stay),
        "age": age,
        "sexe": sex,
        "mode_entree": entry,
        "mode_sortie": exit_mode,
    }


def generate_admissions(rng: np.random.Generator, start: str, end: str, scale: float) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    stays: list[dict] = []
    for code, _label, _pole, beds, mean_los, _rdv in SERVICES:
        if beds == 0:
            continue
        for day in days:
            season = 1 + 0.12 * np.cos(2 * np.pi * (day.dayofyear - 20) / 365.25)  # pic hivernal
            for _ in range(rng.poisson(0.78 * season * beds / mean_los * scale)):
                stays.append(_simulate_stay(rng, code, day, mean_los))

    rows = []
    for i, s in enumerate(stays, start=1):
        r = rng.random()
        sortie = s["sortie"]
        if r < 0.03:
            sortie_txt, exit_txt = "", ""  # sortie non renseignée
        else:
            if rng.random() < 0.01:  # anomalie : sortie antérieure à l'entrée
                sortie = s["entree"] - pd.Timedelta(days=int(rng.integers(1, 6)))
            sortie_txt = _dirty_date(sortie, rng)
            exit_txt = _choice(rng, EXIT_VARIANTS[s["mode_sortie"]])
        label = (
            "Néonatologie"  # service absent du référentiel
            if rng.random() < 0.003
            else (DIRTY_LABELS[s["service"]][0] if rng.random() < 0.6 else _choice(rng, DIRTY_LABELS[s["service"]]))
        )
        age = s["age"]
        age_txt = str(age)
        ra = rng.random()
        if ra < 0.005:
            age_txt = str(_choice(rng, ["-1", "150", "999"]))
        elif ra < 0.015:
            age_txt = ""
        sex_txt = "" if rng.random() < 0.015 else _choice(rng, SEX_VARIANTS[s["sexe"]])
        rows.append(
            {
                "ID_ADM": f"ADM{i:07d}",
                "ID_PATIENT": _dirty_patient_id(s["patient"], rng),
                "DATE_ENTREE": _dirty_date(s["entree"], rng),
                "DATE_SORTIE": sortie_txt,
                "SERVICE": label,
                "MODE_ENTREE": _choice(rng, ENTRY_VARIANTS[s["mode_entree"]]),
                "AGE": age_txt,
                "SEXE": sex_txt,
                "MODE_SORTIE": exit_txt,
            }
        )
    df = pd.DataFrame(rows)
    dups = df.sample(frac=0.02, random_state=int(rng.integers(0, 10_000)))  # doublons exacts
    return pd.concat([df, dups]).sample(frac=1.0, random_state=1).reset_index(drop=True)


def generate_consultations(rng: np.random.Generator, start: str, end: str, scale: float) -> list[dict]:
    records: list[dict] = []
    counter = 0
    for code, _label, _pole, _beds, _los, per_day in SERVICES:
        if per_day == 0:
            continue
        for day in pd.date_range(start, end, freq="D"):
            if day.dayofweek >= 5:
                continue
            for _ in range(rng.poisson(per_day * scale)):
                counter += 1
                status = str(rng.choice(["Honoré", "Absent", "Annulé"], p=[0.78, 0.10, 0.12]))
                ts = day + pd.Timedelta(hours=int(rng.integers(8, 18)), minutes=int(rng.choice([0, 15, 30, 45])))
                date_txt = ts.strftime("%Y-%m-%dT%H:%M:%S") if rng.random() < 0.9 else ts.strftime("%d/%m/%Y %H:%M")
                duration = None
                if status == "Honoré":
                    duration = int(np.clip(rng.normal(20 if code == "RAD" else 25, 7), 5, 90))
                    rd = rng.random()
                    if rd < 0.012:
                        duration = -5
                    elif rd < 0.022:
                        duration = None
                age = int(rng.integers(0, 18)) if code == "PED" else int(np.clip(rng.normal(50, 20), 18, 95))
                rc = rng.random()
                code_txt = code if rc < 0.85 else (code.lower() if rc < 0.95 else code + " ")
                records.append(
                    {
                        "rdv_id": f"RDV{counter:07d}",
                        "patient": {
                            "id": _dirty_patient_id(int(rng.integers(1, 12000)), rng),
                            "age": None if rng.random() < 0.01 else age,
                        },
                        "service_code": code_txt,
                        "date_heure": date_txt,
                        "statut": _choice(rng, STATUS_VARIANTS[status]),
                        "duree_min": duration,
                    }
                )
    n_dup = int(len(records) * 0.015)
    for i in rng.choice(len(records), size=n_dup, replace=False):
        records.append(dict(records[int(i)]))
    order = rng.permutation(len(records))
    return [records[int(i)] for i in order]


def write_services_excel(path: Path) -> None:
    """Référentiel Excel avec titre au-dessus de l'en-tête et ligne de total (cas fréquent en pratique)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Referentiel"
    ws.append(["Référentiel des services - export administratif"])
    ws.append([])
    ws.append(["Code service", "Libellé", "Pôle", "Lits installés"])
    for code, label, pole, beds, _los, _rdv in SERVICES:
        ws.append([code, label, pole, beds])
    ws.append([None, "Total", None, sum(s[3] for s in SERVICES)])
    wb.save(path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="data/raw", help="dossier de sortie")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scale", type=float, default=1.0, help="multiplicateur de volume (tests : 0.05)")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    admissions = generate_admissions(rng, args.start, args.end, args.scale)
    admissions.to_csv(out / "admissions.csv", sep=";", index=False)
    write_services_excel(out / "services.xlsx")
    consultations = generate_consultations(rng, args.start, args.end, args.scale)
    with open(out / "consultations.json", "w", encoding="utf-8") as fh:
        json.dump({"meta": {"source": "outil_rdv", "version": "2.3"}, "rendez_vous": consultations}, fh, ensure_ascii=False)
    print(f"admissions.csv : {len(admissions)} lignes | consultations.json : {len(consultations)} rendez-vous | services.xlsx")


if __name__ == "__main__":
    main()
