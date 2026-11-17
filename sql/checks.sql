-- Contrôles de cohérence après chargement. Le premier échec arrête l'exécution
-- (à lancer avec : psql -v ON_ERROR_STOP=1 -f sql/checks.sql).

DO $$
DECLARE
    n BIGINT;
BEGIN
    -- Les totaux de la table de KPI doivent retrouver ceux des faits.
    SELECT (SELECT SUM(nb_admissions) FROM kpi_monthly_service) - (SELECT COUNT(*) FROM fact_admission) INTO n;
    IF n <> 0 THEN
        RAISE EXCEPTION 'kpi_monthly_service.nb_admissions ne correspond pas à fact_admission (écart %)', n;
    END IF;

    SELECT (SELECT SUM(nb_rdv) FROM kpi_monthly_service) - (SELECT COUNT(*) FROM fact_consultation) INTO n;
    IF n <> 0 THEN
        RAISE EXCEPTION 'kpi_monthly_service.nb_rdv ne correspond pas à fact_consultation (écart %)', n;
    END IF;

    -- Chaque mois de la table de KPI doit exister dans la dimension date.
    SELECT COUNT(*) INTO n
    FROM kpi_monthly_service k
    LEFT JOIN dim_date d ON d.date = k.mois_debut
    WHERE d.date IS NULL;
    IF n <> 0 THEN
        RAISE EXCEPTION '% mois de kpi_monthly_service absents de dim_date', n;
    END IF;

    -- Une grille complète : un enregistrement par mois et par service.
    SELECT (SELECT COUNT(*) FROM kpi_monthly_service)
         - (SELECT COUNT(DISTINCT mois_debut) FROM kpi_monthly_service) * (SELECT COUNT(*) FROM dim_service)
    INTO n;
    IF n <> 0 THEN
        RAISE EXCEPTION 'grille mois x service incomplète (écart %)', n;
    END IF;

    -- La prévision ne doit contenir que des mois postérieurs à l'historique.
    SELECT COUNT(*) INTO n
    FROM forecast_admissions f
    WHERE f.type = 'prévision'
      AND f.mois_debut <= (SELECT MAX(mois_debut) FROM forecast_admissions WHERE type = 'historique');
    IF n <> 0 THEN
        RAISE EXCEPTION '% mois de prévision ne sont pas postérieurs à l''historique', n;
    END IF;

    RAISE NOTICE 'Contrôles de cohérence : OK';
END
$$;
