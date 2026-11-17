# Hôpital : KPI d'activité, pipeline qualité de données, base PostgreSQL et prévision

> Le projet reproduit une problématique courante en milieu hospitalier : consolider des sources hétérogènes, fiabiliser les données, puis alimenter des tableaux de bord de pilotage. Il reprend, sur **données synthétiques** (les données réelles de l'hôpital sont confidentielles), le travail réalisé pendant mon stage.

![Vue d'ensemble de l'activité](docs/img/01-vue-ensemble.png)

| Consultations | Qualité des données | Prévision |
|---|---|---|
| [![](docs/img/02-consultations.png)](docs/img/02-consultations.png) | [![](docs/img/03-qualite.png)](docs/img/03-qualite.png) | [![](docs/img/04-prevision.png)](docs/img/04-prevision.png) |

*Aperçus générés par Python (`make figures`), avec les mêmes indicateurs que les mesures DAX. Le rapport Power BI (`.pbix`) se construit à partir des tables produites en suivant [`powerbi/GUIDE.md`](powerbi/GUIDE.md) : il n'est pas encore versionné.*

**Statut** : pipeline, base PostgreSQL, analyse et prévision terminés et testés (37 tests). Rapport Power BI : modèle, mesures DAX et guide fournis, `.pbix` à construire. Source publique SAE (DREES) : code d'ingestion fourni, fichier à télécharger ([`data/external/README.md`](data/external/README.md)).

## Ce que montrent les données (graine 42, données synthétiques)

- **Pression sur les lits :** les urgences ont le taux d'occupation le plus élevé (86,7 %), au-dessus du seuil de tension de 80 % (limite : un séjour d'un jour compte pour 1 jour-lit).
- **Saisonnalité :** pic en décembre (indice 1,15) et creux en septembre (0,89), soit 1,29 fois plus d'activité au pic. Elle est codée dans le générateur : le résultat valide la méthode, pas un phénomène réel.
- **Prévision à 3 mois :** la méthode saisonnière naïve corrigée de la croissance fait une erreur moyenne de 45 admissions par mois en backtest, contre 101 pour la méthode naïve. Lecture complète dans [`reports/analyse.md`](reports/analyse.md).

## Problème

Trois systèmes exportent leurs données chacun à leur manière : formats de dates mixtes, libellés de services différents, doublons, valeurs aberrantes. Sans fiabilisation, les indicateurs d'activité (durée moyenne de séjour, taux d'occupation, absentéisme en consultation) sont faux ou non comparables.

## Solution

```
 Sources brutes (hétérogènes)         Nettoyage et contrôle              Modèle analytique                 Restitution
 ┌──────────────────────────┐   ┌───────────────────────────────┐   ┌──────────────────────────┐   ┌─────────────────────┐
 │ admissions.csv  (CSV ;)  │   │ dédoublonnage, dates, libellés │   │ dim_service, dim_date    │   │ PostgreSQL          │
 │ services.xlsx   (Excel)  │──►│ identifiants, valeurs aberrantes│──►│ fact_admission           │──►│  (clés, contraintes,│
 │ consultations.json (JSON)│   │ quarantaine + rapport qualité  │   │ fact_consultation        │   │   requêtes SQL)     │
 └──────────────────────────┘   └───────────────────────────────┘   │ kpi_monthly_service      │   │ Power BI (DAX)      │
                                                                     │ forecast_admissions      │   │ analyse + prévision │
                                                                     └──────────────────────────┘   └─────────────────────┘
```

- **Intégration** de 3 sources de formats différents (CSV, Excel avec en-tête décalé, JSON imbriqué), ~80 000 lignes brutes.
- **Nettoyage tracé** : chaque règle est comptée et journalisée ; les lignes inutilisables vont en quarantaine avec leur motif (`reports/rejected_*.csv`), jamais supprimées en silence.
- **Modèle en étoile** (2 dimensions, 2 faits, 1 table de KPI mensuels) avec contrôles d'intégrité bloquants (clés primaires uniques, clés étrangères valides).
- **PostgreSQL** : le même modèle est chargé dans une base qui impose elle-même clés primaires, clés étrangères, domaines de valeurs et cohérence des dates (`sql/schema.sql`), avec 7 requêtes d'analyse (`sql/analyses.sql`) et des contrôles de cohérence (`sql/checks.sql`), rejoués en CI sur une vraie base.
- **Analyse et prévision** : tendance, indice saisonnier, pression sur les lits, prévision à 3 mois validée par un backtest à origine glissante.
- **Reproductibilité** : données générées avec graine fixe, tout se reconstruit en une commande, tests automatisés, Docker, intégration continue GitHub Actions.

## Résultats du nettoyage (exécution par défaut, graine 42)

| Source | Lignes brutes | Doublons | Rejetées | Propres |
|---|---:|---:|---:|---:|
| admissions | 30 694 | 602 | 380 | 29 712 |
| consultations | 49 423 | 730 | 0 | 48 693 |

Anomalies traitées : doublons, dates de sortie antérieures à l'entrée (314), services inconnus (66), âges aberrants (151), durées de consultation négatives ou manquantes (812), dates de sortie manquantes (905). Détail complet dans [`reports/quality_report.md`](reports/quality_report.md).

## Lancer le projet

```bash
make install     # dépendances Python
make all         # génère les données, exécute le pipeline, l'analyse, lance les tests
make figures     # (re)génère les aperçus dans docs/img
# ou, avec Docker :
make docker-build && make docker-run
```

Sorties : `data/processed/*.csv` (tables pour Power BI et PostgreSQL), `reports/quality_report.md`, `reports/analyse.md`.

### Base PostgreSQL

```bash
make db-up       # démarre PostgreSQL dans Docker
make db-load     # crée le schéma (clés, contraintes) et charge les 6 tables (client psql requis)
make db-check    # contrôles de cohérence SQL
make db-query    # exécute les 7 requêtes d'analyse
make db-down
```

La chaîne de connexion par défaut est `postgresql://hkpi:hkpi@localhost:5432/hopital` (variable `DATABASE_URL`).

## Indicateurs

| Indicateur | Définition |
|---|---|
| Durée moyenne de séjour (DMS) | Moyenne de (date de sortie - date d'entrée) sur les séjours terminés |
| Taux d'occupation | Jours-lits occupés / (lits installés x jours du mois), en rapport de sommes |
| Part d'entrées par les urgences | Admissions via les urgences / admissions |
| Taux d'absence en consultation | Rendez-vous « absent » / rendez-vous total |

## Structure

```
src/hkpi/      generate.py (sources synthétiques) · clean.py (règles) · model.py (étoile, KPI)
               quality.py (rapport) · pipeline.py (orchestration + contrôles)
               analysis.py (tendance, saisonnalité, rapport) · forecast.py (prévision, backtest)
               figures.py (aperçus PNG) · sae.py (source publique optionnelle)
sql/           schema.sql · load.sql · checks.sql · analyses.sql (PostgreSQL)
tests/         37 tests (nettoyage, intégrité, KPI, reproductibilité, analyse, prévision, SAE)
powerbi/       guide (5 pages), schéma du modèle, mesures DAX
docs/          COMPRENDRE.md (choix techniques, questions d'entretien) · img/ (aperçus)
data/external/ source publique SAE (à télécharger, étape optionnelle)
```

## Limites assumées

- Premier mois sans taux d'occupation (séjours antérieurs à l'export absents).
- Séjours sans date de sortie exclus de la DMS et de l'occupation.
- Séjour d'un jour compté pour 1 jour-lit (surestime l'occupation des urgences).
- Données synthétiques : les valeurs illustrent la méthode, pas une réalité clinique. En particulier, la saisonnalité retrouvée par l'analyse est celle du générateur.
- Prévision sur 24 mois d'historique seulement : méthode volontairement simple (un modèle saisonnier complet demanderait plus de cycles).
- Le schéma PostgreSQL et les requêtes ont été validés en local sur SQLite (contraintes, ordre des colonnes, résultats) ; l'exécution sur PostgreSQL est celle du job `postgres` de la CI.
- Le fichier SAE n'est pas versionné et les noms de ses colonnes n'ont pas pu être vérifiés au moment de l'écriture : voir `data/external/README.md`.

## Stack

Python (pandas, NumPy, matplotlib, openpyxl) · pytest · PostgreSQL 16 (SQL, contraintes) · Docker / Docker Compose · GitHub Actions · Make · Power BI (DAX, modélisation en étoile)
