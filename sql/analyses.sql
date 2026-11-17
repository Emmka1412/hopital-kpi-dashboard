-- Requêtes d'analyse sur le modèle en étoile (PostgreSQL).
-- Les colonnes décimales sont en NUMERIC, donc ROUND(x, n) fonctionne sans conversion.
-- Les ratios sont des rapports de sommes, jamais des moyennes de taux (voir docs/COMPRENDRE.md).

-- 1. Volume et durée moyenne de séjour par service
SELECT s.libelle,
       COUNT(*)                          AS admissions,
       ROUND(AVG(f.duree_sejour_j), 2)   AS dms_jours
FROM fact_admission f
JOIN dim_service s ON s.code_service = f.service_code
GROUP BY s.libelle
ORDER BY admissions DESC;

-- 2. Entrées par les urgences : série mensuelle et moyenne mobile sur 3 mois
SELECT mois_debut,
       SUM(nb_entrees_urgences) AS entrees_urgences,
       ROUND(AVG(SUM(nb_entrees_urgences)) OVER (
             ORDER BY mois_debut ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moyenne_mobile_3m
FROM kpi_monthly_service
GROUP BY mois_debut
ORDER BY mois_debut;

-- 3. Taux d'absence en consultation par service
SELECT s.libelle,
       ROUND(1.0 * SUM(k.nb_absents) / SUM(k.nb_rdv), 4) AS taux_absence
FROM kpi_monthly_service k
JOIN dim_service s ON s.code_service = k.service_code
WHERE k.nb_rdv > 0
GROUP BY s.libelle
ORDER BY taux_absence DESC;

-- 4. Taux d'occupation par service (services avec lits, premier mois exclu)
SELECT s.libelle,
       ROUND(1.0 * SUM(k.jours_lit_occupes) / SUM(k.jours_lit_disponibles), 3) AS occupation
FROM kpi_monthly_service k
JOIN dim_service s ON s.code_service = k.service_code
WHERE k.jours_lit_disponibles > 0
GROUP BY s.libelle
ORDER BY occupation DESC;

-- 5. Durée de séjour selon la tranche d'âge
SELECT tranche_age,
       COUNT(*)                        AS sejours,
       ROUND(AVG(duree_sejour_j), 2)   AS dms_jours
FROM fact_admission
GROUP BY tranche_age
ORDER BY dms_jours DESC;

-- 6. Admissions par mois civil : 2024 contre 2025 et évolution (jointure sur la dimension date)
SELECT d.mois,
       d.mois_libelle,
       SUM(CASE WHEN d.annee = 2024 THEN k.nb_admissions END) AS admissions_2024,
       SUM(CASE WHEN d.annee = 2025 THEN k.nb_admissions END) AS admissions_2025,
       ROUND(100.0 * (SUM(CASE WHEN d.annee = 2025 THEN k.nb_admissions END)
                    - SUM(CASE WHEN d.annee = 2024 THEN k.nb_admissions END))
                   / SUM(CASE WHEN d.annee = 2024 THEN k.nb_admissions END), 1) AS evolution_pct
FROM kpi_monthly_service k
JOIN dim_date d ON d.date = k.mois_debut
GROUP BY d.mois, d.mois_libelle
ORDER BY d.mois;

-- 7. Indice saisonnier : activité d'un mois civil rapportée à la moyenne mensuelle (1,00 = mois moyen)
WITH par_mois AS (
    SELECT d.mois, d.mois_libelle, SUM(k.nb_admissions) AS admissions
    FROM kpi_monthly_service k
    JOIN dim_date d ON d.date = k.mois_debut
    GROUP BY d.mois, d.mois_libelle
)
SELECT mois_libelle,
       admissions,
       ROUND(admissions / (SUM(admissions) OVER () / 12.0), 3) AS indice_saisonnier
FROM par_mois
ORDER BY mois;
