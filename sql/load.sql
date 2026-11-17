-- Chargement des CSV produits par le pipeline (à lancer depuis la racine du dépôt).
-- \copy lit les fichiers côté client : il fonctionne avec une base locale, Docker ou distante.
-- Ordre imposé par les clés étrangères : dimensions d'abord, faits ensuite.

\copy dim_service FROM 'data/processed/dim_service.csv' WITH (FORMAT csv, HEADER true)
\copy dim_date FROM 'data/processed/dim_date.csv' WITH (FORMAT csv, HEADER true)
\copy fact_admission FROM 'data/processed/fact_admission.csv' WITH (FORMAT csv, HEADER true)
\copy fact_consultation FROM 'data/processed/fact_consultation.csv' WITH (FORMAT csv, HEADER true)
\copy kpi_monthly_service FROM 'data/processed/kpi_monthly_service.csv' WITH (FORMAT csv, HEADER true)
\copy forecast_admissions FROM 'data/processed/forecast_admissions.csv' WITH (FORMAT csv, HEADER true)
