-- Schéma PostgreSQL du modèle en étoile.
-- La base impose elle-même l'intégrité que `check_integrity` (pipeline.py) vérifie en Python :
-- clés primaires, clés étrangères, domaines de valeurs, cohérence des dates.
-- Rejouable : tout est supprimé puis recréé.

DROP TABLE IF EXISTS forecast_admissions;
DROP TABLE IF EXISTS kpi_monthly_service;
DROP TABLE IF EXISTS fact_consultation;
DROP TABLE IF EXISTS fact_admission;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_service;

CREATE TABLE dim_service (
    code_service TEXT PRIMARY KEY,
    libelle      TEXT NOT NULL,
    pole         TEXT NOT NULL,
    lits         INTEGER NOT NULL CHECK (lits >= 0)
);

CREATE TABLE dim_date (
    date             DATE PRIMARY KEY,
    annee            INTEGER NOT NULL,
    trimestre        INTEGER NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mois             INTEGER NOT NULL CHECK (mois BETWEEN 1 AND 12),
    mois_libelle     TEXT NOT NULL,
    mois_debut       DATE NOT NULL,
    annee_mois       TEXT NOT NULL,
    jour_semaine_num INTEGER NOT NULL CHECK (jour_semaine_num BETWEEN 1 AND 7),
    jour_semaine     TEXT NOT NULL,
    est_weekend      BOOLEAN NOT NULL
);

CREATE TABLE fact_admission (
    adm_id         TEXT PRIMARY KEY,
    patient_id     TEXT NOT NULL,
    date_entree    DATE NOT NULL REFERENCES dim_date (date),
    date_sortie    DATE REFERENCES dim_date (date),
    service_code   TEXT NOT NULL REFERENCES dim_service (code_service),
    mode_entree    TEXT NOT NULL,
    mode_sortie    TEXT,
    age            NUMERIC(5, 1) CHECK (age BETWEEN 0 AND 110),
    sexe           TEXT NOT NULL CHECK (sexe IN ('M', 'F', 'NR')),
    duree_sejour_j NUMERIC CHECK (duree_sejour_j >= 0),
    tranche_age    TEXT NOT NULL,
    CHECK (date_sortie IS NULL OR date_sortie >= date_entree)
);

CREATE TABLE fact_consultation (
    rdv_id       TEXT PRIMARY KEY,
    patient_id   TEXT NOT NULL,
    date_rdv     DATE NOT NULL REFERENCES dim_date (date),
    heure_rdv    TIME NOT NULL,
    service_code TEXT NOT NULL REFERENCES dim_service (code_service),
    statut       TEXT NOT NULL CHECK (statut IN ('Honoré', 'Absent', 'Annulé')),
    duree_min    NUMERIC CHECK (duree_min > 0),
    age          NUMERIC(5, 1)
);

CREATE TABLE kpi_monthly_service (
    mois_debut             DATE NOT NULL,
    service_code           TEXT NOT NULL REFERENCES dim_service (code_service),
    nb_admissions          INTEGER NOT NULL,
    nb_sejours_termines    INTEGER NOT NULL,
    dms_jours              NUMERIC,
    nb_entrees_urgences    INTEGER NOT NULL,
    nb_deces               INTEGER NOT NULL,
    nb_rdv                 INTEGER NOT NULL,
    nb_honores             INTEGER NOT NULL,
    nb_absents             INTEGER NOT NULL,
    nb_annules             INTEGER NOT NULL,
    duree_moyenne_rdv_min  NUMERIC,
    jours_lit_occupes      NUMERIC,
    jours_lit_disponibles  NUMERIC,
    taux_occupation        NUMERIC CHECK (taux_occupation BETWEEN 0 AND 1),
    part_entrees_urgences  NUMERIC CHECK (part_entrees_urgences BETWEEN 0 AND 1),
    taux_absence           NUMERIC CHECK (taux_absence BETWEEN 0 AND 1),
    PRIMARY KEY (mois_debut, service_code)
);

CREATE TABLE forecast_admissions (
    mois_debut DATE PRIMARY KEY,
    admissions NUMERIC NOT NULL,
    type       TEXT NOT NULL CHECK (type IN ('historique', 'prévision'))
);

CREATE INDEX idx_fact_admission_service ON fact_admission (service_code);
CREATE INDEX idx_fact_admission_entree ON fact_admission (date_entree);
CREATE INDEX idx_fact_consultation_service ON fact_consultation (service_code);
CREATE INDEX idx_fact_consultation_date ON fact_consultation (date_rdv);
