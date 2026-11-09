"""Règles de nettoyage et de normalisation des sources brutes.

Principe : chaque règle est explicite, comptée et journalisée (``QualityLog``). Une ligne est soit
corrigée, soit conservée avec une valeur vide, soit rejetée dans un fichier de quarantaine avec son motif.
On ne supprime jamais une ligne sans trace.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

# --------------------------------------------------------------------------- journal qualité


@dataclass
class QualityLog:
    entries: list[dict] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, source: str, rule: str, count: int, action: str) -> None:
        if count:
            self.entries.append({"source": source, "regle": rule, "nombre": int(count), "traitement": action})

    def set_counts(self, source: str, raw: int, duplicates: int, rejected: int, clean: int) -> None:
        self.counts[source] = {"brutes": raw, "doublons": duplicates, "rejetees": rejected, "propres": clean}

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries, columns=["source", "regle", "nombre", "traitement"])


# --------------------------------------------------------------------------- briques de normalisation


def normalise_text(value) -> str:
    """Minuscules, sans accents ni ponctuation : « Méd. interne » -> « med interne »."""
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_SERVICE_ALIASES = {
    "URG": ["urgences", "urg", "service des urgences"],
    "CAR": ["cardiologie", "cardio"],
    "PED": ["pediatrie", "ped"],
    "CHI": ["chirurgie", "chir", "chirurgie generale"],
    "MAT": ["maternite", "mat"],
    "MIN": ["medecine interne", "med interne"],
    "REA": ["reanimation", "rea"],
    "RAD": ["radiologie", "radio", "imagerie"],
}
_ALIAS_TO_CODE = {alias: code for code, aliases in _SERVICE_ALIASES.items() for alias in aliases}


def map_service(series: pd.Series, valid_codes) -> pd.Series:
    """Ramène libellés et codes variables vers le code officiel du référentiel (ou vide si inconnu)."""
    valid = {str(c).upper() for c in valid_codes}

    def _one(value):
        text = normalise_text(value)
        if not text:
            return None
        if text.upper() in valid:
            return text.upper()
        code = _ALIAS_TO_CODE.get(text)
        return code if code in valid else None

    return series.map(_one)


def normalise_patient_id(series: pd.Series) -> pd.Series:
    """« p123 », « 123 », « P000123 » -> « P000123 »."""
    digits = series.astype("string").str.extract(r"(\d+)", expand=False)
    return "P" + digits.str.zfill(6)


def parse_dates(series: pd.Series, formats: list[tuple[str, str]]) -> pd.Series:
    """Parse des dates à formats mixtes avec un format explicite par motif (pas de devinette dd/mm vs mm/dd)."""
    text = series.astype("string").str.strip()
    result = None
    for pattern, fmt in formats:
        mask = text.str.fullmatch(pattern).fillna(False)
        part = pd.to_datetime(text.where(mask), format=fmt, errors="coerce")
        result = part if result is None else result.fillna(part)
    return result.astype("datetime64[ns]")


def _map_labels(series: pd.Series, mapping: dict[str, str], unknown: str, empty) -> pd.Series:
    def _one(value):
        text = normalise_text(value)
        if not text:
            return empty
        return mapping.get(text, unknown)

    return series.map(_one)


SEX_MAP = {"m": "M", "h": "M", "masculin": "M", "homme": "M", "f": "F", "feminin": "F", "femme": "F"}
ENTRY_MAP = {
    "urgences": "Urgences",
    "urgence": "Urgences",
    "programmee": "Programmée",
    "programme": "Programmée",
    "prog": "Programmée",
    "transfert": "Transfert",
}
EXIT_MAP = {"domicile": "Domicile", "transfert": "Transfert", "deces": "Décès", "autre": "Autre"}
STATUS_MAP = {
    "honore": "Honoré",
    "realise": "Honoré",
    "absent": "Absent",
    "no show": "Absent",
    "annule": "Annulé",
}

ADM_DATE_FORMATS = [
    (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
    (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),
    (r"\d{2}-\d{2}-\d{4}", "%d-%m-%Y"),
]
RDV_DATE_FORMATS = [
    (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "%Y-%m-%dT%H:%M:%S"),
    (r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", "%d/%m/%Y %H:%M"),
]


def _reject(df: pd.DataFrame, mask: pd.Series, rule: str, source: str, log: QualityLog, bucket: list) -> pd.DataFrame:
    mask = mask.fillna(False).astype(bool)
    if mask.any():
        bucket.append(df[mask].assign(motif_rejet=rule))
        log.add(source, rule, int(mask.sum()), "rejeté (quarantaine)")
    return df[~mask]


def _concat_rejected(bucket: list, columns) -> pd.DataFrame:
    return pd.concat(bucket) if bucket else pd.DataFrame(columns=[*columns, "motif_rejet"])


# --------------------------------------------------------------------------- référentiel services


def clean_services(raw: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    df = raw.copy()
    renamed = {}
    for col in df.columns:
        key = normalise_text(col)
        if key.startswith("code"):
            renamed[col] = "code_service"
        elif key.startswith("libelle"):
            renamed[col] = "libelle"
        elif key.startswith("pole"):
            renamed[col] = "pole"
        elif key.startswith("lits"):
            renamed[col] = "lits"
    df = df.rename(columns=renamed)[["code_service", "libelle", "pole", "lits"]]
    ignored = df["code_service"].isna()
    log.add("services", "ligne_hors_service (total, vide)", int(ignored.sum()), "ignorée")
    df = df[~ignored].copy()
    df["code_service"] = df["code_service"].astype(str).str.strip().str.upper()
    df["libelle"] = df["libelle"].astype(str).str.strip()
    df["pole"] = df["pole"].astype(str).str.strip()
    df["lits"] = pd.to_numeric(df["lits"], errors="coerce").fillna(0).astype(int)
    df = df.drop_duplicates(subset="code_service").reset_index(drop=True)
    log.set_counts("services", len(raw), 0, int(ignored.sum()), len(df))
    return df


# --------------------------------------------------------------------------- admissions

ADM_COLUMNS = [
    "adm_id", "patient_id", "date_entree", "date_sortie", "service_code",
    "mode_entree", "mode_sortie", "age", "sexe", "duree_sejour_j",
]  # fmt: skip


def clean_admissions(raw: pd.DataFrame, valid_codes, log: QualityLog) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = "admissions"
    df = raw.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].astype("string").str.strip()
    n_raw = len(df)
    rejected: list[pd.DataFrame] = []

    df["id_adm"] = df["id_adm"].str.upper()
    df = _reject(df, df["id_adm"].isna(), "id_adm_manquant", source, log, rejected)

    dup = df.duplicated(subset="id_adm", keep="first")
    n_dup = int(dup.sum())
    log.add(source, "doublon_id_adm", n_dup, "supprimé (première occurrence conservée)")
    df = df[~dup].copy()

    df["patient_id"] = normalise_patient_id(df["id_patient"])
    df = _reject(df, df["patient_id"].isna(), "id_patient_invalide", source, log, rejected)

    df["date_entree"] = parse_dates(df["date_entree"], ADM_DATE_FORMATS)
    df = _reject(df, df["date_entree"].isna(), "date_entree_illisible", source, log, rejected)

    raw_exit = df["date_sortie"]
    df["date_sortie"] = parse_dates(raw_exit, ADM_DATE_FORMATS)
    log.add(source, "date_sortie_manquante", int(raw_exit.isna().sum()), "conservé (exclu des durées de séjour)")
    log.add(source, "date_sortie_illisible", int((raw_exit.notna() & df["date_sortie"].isna()).sum()), "valeur vidée")
    df = _reject(df, df["date_sortie"] < df["date_entree"], "date_sortie_avant_entree", source, log, rejected)

    df["service_code"] = map_service(df["service"], valid_codes)
    df = _reject(df, df["service_code"].isna(), "service_inconnu", source, log, rejected)

    age = pd.to_numeric(df["age"], errors="coerce")
    aberrant = age.notna() & ~age.between(0, 110)
    log.add(source, "age_manquant", int(age.isna().sum()), "conservé (âge vide)")
    log.add(source, "age_aberrant (hors 0-110)", int(aberrant.sum()), "valeur vidée")
    df["age"] = age.where(~aberrant)

    df["sexe"] = _map_labels(df["sexe"], SEX_MAP, unknown="NR", empty="NR")
    df["mode_entree"] = _map_labels(df["mode_entree"], ENTRY_MAP, unknown="Autre", empty="Non renseigné")
    df["mode_sortie"] = _map_labels(df["mode_sortie"], EXIT_MAP, unknown="Autre", empty=None)
    df["duree_sejour_j"] = (df["date_sortie"] - df["date_entree"]).dt.days
    df = df.rename(columns={"id_adm": "adm_id"})[ADM_COLUMNS].reset_index(drop=True)

    rejected_df = _concat_rejected(rejected, raw.columns)
    log.set_counts(source, n_raw, n_dup, len(rejected_df), len(df))
    return df, rejected_df


# --------------------------------------------------------------------------- consultations

RDV_COLUMNS = ["rdv_id", "patient_id", "date_rdv", "heure_rdv", "service_code", "statut", "duree_min", "age"]


def clean_consultations(raw: pd.DataFrame, valid_codes, log: QualityLog) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = "consultations"
    df = raw.copy().rename(columns={"patient.id": "id_patient", "patient.age": "age"})
    for col in ["rdv_id", "id_patient", "service_code", "date_heure", "statut"]:
        df[col] = df[col].astype("string").str.strip()
    n_raw = len(df)
    rejected: list[pd.DataFrame] = []

    df = _reject(df, df["rdv_id"].isna(), "rdv_id_manquant", source, log, rejected)
    dup = df.duplicated(subset="rdv_id", keep="first")
    n_dup = int(dup.sum())
    log.add(source, "doublon_rdv_id", n_dup, "supprimé (première occurrence conservée)")
    df = df[~dup].copy()

    df["patient_id"] = normalise_patient_id(df["id_patient"])
    df = _reject(df, df["patient_id"].isna(), "id_patient_invalide", source, log, rejected)

    df["service_code"] = map_service(df["service_code"], valid_codes)
    df = _reject(df, df["service_code"].isna(), "service_inconnu", source, log, rejected)

    stamp = parse_dates(df["date_heure"], RDV_DATE_FORMATS)
    df = _reject(df.assign(_stamp=stamp), stamp.isna(), "date_rdv_illisible", source, log, rejected)
    df["date_rdv"] = df["_stamp"].dt.normalize()
    df["heure_rdv"] = df["_stamp"].dt.strftime("%H:%M")

    df["statut"] = _map_labels(df["statut"], STATUS_MAP, unknown="Inconnu", empty="Inconnu")
    df = _reject(df, df["statut"] == "Inconnu", "statut_inconnu", source, log, rejected)

    duration = pd.to_numeric(df["duree_min"], errors="coerce")
    honored = df["statut"] == "Honoré"
    bad = honored & (duration.isna() | (duration <= 0))
    log.add(source, "duree_honoree_manquante_ou_negative", int(bad.sum()), "valeur vidée")
    df["duree_min"] = duration.where(honored & ~bad)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df = df[RDV_COLUMNS].reset_index(drop=True)

    rejected_df = _concat_rejected(rejected, raw.columns)
    log.set_counts(source, n_raw, n_dup, len(rejected_df), len(df))
    return df, rejected_df
