import pandas as pd
import pytest

from hkpi.clean import (
    ADM_DATE_FORMATS,
    QualityLog,
    clean_admissions,
    clean_consultations,
    map_service,
    normalise_patient_id,
    normalise_text,
    parse_dates,
)

CODES = ["URG", "CAR", "PED", "CHI", "MAT", "MIN", "REA", "RAD"]


def _adm(**overrides):
    row = {
        "ID_ADM": "ADM0000001", "ID_PATIENT": "P000012", "DATE_ENTREE": "02/03/2024", "DATE_SORTIE": "05/03/2024",
        "SERVICE": "Cardiologie", "MODE_ENTREE": "Urgences", "AGE": "70", "SEXE": "H", "MODE_SORTIE": "Domicile",
    }  # fmt: skip
    row.update(overrides)
    return row


def test_normalise_text_removes_accents_and_punctuation():
    assert normalise_text("Méd. interne") == "med interne"
    assert normalise_text(None) == ""


def test_parse_dates_handles_mixed_formats_without_day_month_confusion():
    s = pd.Series(["02/03/2024", "2024-03-02", "02-03-2024", "n'importe quoi", None])
    out = parse_dates(s, ADM_DATE_FORMATS)
    assert out.iloc[0] == out.iloc[1] == out.iloc[2] == pd.Timestamp("2024-03-02")  # 2 mars, pas 3 février
    assert out.iloc[3:].isna().all()


@pytest.mark.parametrize("label", ["Urgences", "URGENCES", "urgences ", "Urg.", "urg", "Service des urgences"])
def test_map_service_variants_to_one_code(label):
    assert map_service(pd.Series([label]), CODES).iloc[0] == "URG"


def test_map_service_unknown_is_none():
    assert map_service(pd.Series(["Néonatologie"]), CODES).iloc[0] is None


def test_normalise_patient_id():
    out = normalise_patient_id(pd.Series(["P000123", "p123", "123", "abc"]))
    assert out.iloc[:3].tolist() == ["P000123"] * 3
    assert pd.isna(out.iloc[3])


def test_clean_admissions_dedup_and_reject_inverted_dates():
    raw = pd.DataFrame(
        [
            _adm(),
            _adm(),  # doublon exact
            _adm(ID_ADM="ADM0000002", DATE_SORTIE="01/03/2024"),  # sortie avant entrée -> rejet
            _adm(ID_ADM="ADM0000003", SERVICE="Néonatologie"),  # service inconnu -> rejet
        ]
    )
    log = QualityLog()
    clean, rejected = clean_admissions(raw, CODES, log)
    assert len(clean) == 1
    assert set(rejected["motif_rejet"]) == {"date_sortie_avant_entree", "service_inconnu"}
    c = log.counts["admissions"]
    assert c["brutes"] == c["doublons"] + c["rejetees"] + c["propres"] == 4


def test_clean_admissions_normalises_values_and_keeps_incomplete_rows():
    raw = pd.DataFrame(
        [
            _adm(AGE="999", SEXE="Masculin"),
            _adm(ID_ADM="ADM0000002", DATE_SORTIE=None, MODE_SORTIE=None, SEXE=None),
        ]
    )
    clean, rejected = clean_admissions(raw, CODES, QualityLog())
    assert rejected.empty
    first, second = clean.iloc[0], clean.iloc[1]
    assert pd.isna(first["age"]) and first["sexe"] == "M" and first["duree_sejour_j"] == 3
    assert pd.isna(second["date_sortie"]) and pd.isna(second["duree_sejour_j"]) and second["sexe"] == "NR"


def test_clean_consultations_status_duration_and_formats():
    raw = pd.DataFrame(
        [
            {"rdv_id": "R1", "service_code": "car ", "date_heure": "2024-03-04T09:30:00", "statut": "réalisé", "duree_min": 25, "patient.id": "p5", "patient.age": 40},
            {"rdv_id": "R2", "service_code": "CAR", "date_heure": "04/03/2024 10:00", "statut": "no show", "duree_min": None, "patient.id": "5", "patient.age": None},
            {"rdv_id": "R3", "service_code": "CAR", "date_heure": "2024-03-04T11:00:00", "statut": "HONORE", "duree_min": -5, "patient.id": "6", "patient.age": 30},
        ]
    )
    clean, rejected = clean_consultations(raw, CODES, QualityLog())
    assert rejected.empty
    assert clean["statut"].tolist() == ["Honoré", "Absent", "Honoré"]
    assert (clean["date_rdv"] == pd.Timestamp("2024-03-04")).all()
    assert clean["heure_rdv"].tolist() == ["09:30", "10:00", "11:00"]
    assert clean["duree_min"].iloc[0] == 25 and pd.isna(clean["duree_min"].iloc[2])
