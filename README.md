# Hôpital : KPI d'activité, pipeline qualité de données et dashboard Power BI

>  Le projet reproduit une problématique courante en milieu hospitalier : consolider des sources hétérogènes, fiabiliser les données, puis alimenter des tableaux de bord de pilotage.

**Statut** : pipeline de données terminé et testé. Dashboard Power BI : modèle, mesures DAX et guide fournis dans [`powerbi/`](powerbi/GUIDE.md), rapport `.pbix` à construire à partir des tables produites.

## Problème

Trois systèmes exportent leurs données chacun à leur manière : formats de dates mixtes, libellés de services différents, doublons, valeurs aberrantes. Sans fiabilisation, les indicateurs d'activité (durée moyenne de séjour, taux d'occupation, absentéisme en consultation) sont faux ou non comparables.

## Solution

```
 Sources brutes (hétérogènes)              Nettoyage et contrôle                 Modèle analytique
 ┌──────────────────────────┐       ┌───────────────────────────────┐      ┌──────────────────────────┐
 │ admissions.csv  (CSV ;)  │       │ dédoublonnage, dates, libellés │      │ dim_service, dim_date    │
 │ services.xlsx   (Excel)  │ ────► │ identifiants, valeurs aberrantes│ ───► │ fact_admission           │ ──► Power BI
 │ consultations.json (JSON)│       │ quarantaine + rapport qualité  │      │ fact_consultation        │
 └──────────────────────────┘       └───────────────────────────────┘      │ kpi_monthly_service      │
                                                                            └──────────────────────────┘
```

- **Intégration** de 3 sources de formats différents (CSV, Excel avec en-tête décalé, JSON imbriqué), ~80 000 lignes brutes.
- **Nettoyage tracé** : chaque règle est comptée et journalisée ; les lignes inutilisables vont en quarantaine avec leur motif (`reports/rejected_*.csv`), jamais supprimées en silence.
- **Modèle en étoile** (2 dimensions, 2 faits, 1 table de KPI mensuels) avec contrôles d'intégrité bloquants (clés primaires uniques, clés étrangères valides).
- **Reproductibilité** : données générées avec graine fixe, tout se reconstruit en une commande, tests automatisés, Docker, intégration continue GitHub Actions.

## Résultats (exécution par défaut, graine 42)

| Source | Lignes brutes | Doublons | Rejetées | Propres |
|---|---:|---:|---:|---:|
| admissions | 30 694 | 602 | 380 | 29 712 |
| consultations | 49 423 | 730 | 0 | 48 693 |

Anomalies traitées : doublons, dates de sortie antérieures à l'entrée (314), services inconnus (66), âges aberrants (151), durées de consultation négatives ou manquantes (812), dates de sortie manquantes (905). Détail complet dans [`reports/quality_report.md`](reports/quality_report.md).

## Lancer le projet

```bash
make install     # dépendances Python
make all         # génère les données, exécute le pipeline, lance les tests
# ou, avec Docker :
make docker-build && make docker-run
```

Sorties : `data/processed/*.csv` (tables pour Power BI) et `reports/quality_report.md`.

## Indicateurs

| Indicateur | Définition |
|---|---|
| Durée moyenne de séjour (DMS) | Moyenne de (date de sortie - date d'entrée) sur les séjours terminés |
| Taux d'occupation | Jours-lits occupés / (lits installés x jours du mois) |
| Part d'entrées par les urgences | Admissions via les urgences / admissions |
| Taux d'absence en consultation | Rendez-vous « absent » / rendez-vous total |

## Structure

```
src/hkpi/      generate.py (sources synthétiques) · clean.py (règles) · model.py (étoile, KPI)
               quality.py (rapport) · pipeline.py (orchestration + contrôles)
tests/         20 tests (règles de nettoyage, intégrité, plages de KPI, reproductibilité)
powerbi/       guide, schéma du modèle, mesures DAX
docs/          COMPRENDRE.md : choix techniques et questions d'entretien
```

## Limites assumées

- Premier mois sans taux d'occupation (séjours antérieurs à l'export absents).
- Séjours sans date de sortie exclus de la DMS et de l'occupation.
- Séjour d'un jour compté pour 1 jour-lit (surestime l'occupation des urgences).
- Données synthétiques : les valeurs illustrent la méthode, pas une réalité clinique.

## Stack

Python (pandas, NumPy, openpyxl) · pytest · Docker / Docker Compose · GitHub Actions · Make · Power BI (DAX, modélisation en étoile)
