<div align="center">

# Hôpital : pipeline qualité de données, KPI et prévision

**Trois exports hospitaliers hétérogènes → nettoyage tracé → modèle en étoile → PostgreSQL, Power BI et prévision**

[![CI](https://github.com/Emmka1412/hopital-kpi-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Emmka1412/hopital-kpi-dashboard/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-37-brightgreen)
![Données](https://img.shields.io/badge/données-synthétiques-orange)

<img src="docs/img/01-vue-ensemble.png" alt="Vue d'ensemble de l'activité : KPI, admissions par mois, occupation par service" width="900">

</div>

> Version publique de mon travail de stage à l'hôpital : les données réelles étant confidentielles, tout est reconstruit sur des **données synthétiques** avec des erreurs injectées volontairement. Ce qui est montré ici, c'est la méthode.

## En bref

- **Intégration** de 3 sources de formats différents (CSV, Excel à en-tête décalé, JSON imbriqué), environ 80 000 lignes brutes.
- **Nettoyage tracé** : chaque règle est comptée, aucune ligne n'est supprimée sans trace (quarantaine avec le motif de rejet).
- **Modèle en étoile** avec contrôles d'intégrité bloquants, chargé dans **PostgreSQL** avec clés et contraintes.
- **Analyse** : tendance, saisonnalité, pression sur les lits, **prévision à 3 mois** validée par backtest.
- **Qualité logicielle** : 37 tests, intégration continue GitHub Actions, Docker, reproductibilité par graine fixe.

## Sommaire

[Architecture](#architecture) · [Résultats](#résultats-graine-42-données-synthétiques) · [Aperçus](#aperçus) · [Lancer le projet](#lancer-le-projet) · [Base PostgreSQL](#base-postgresql) · [Indicateurs](#indicateurs) · [Structure](#structure) · [Limites](#limites-assumées) · [Avancement](#avancement)

## Architecture

```mermaid
flowchart LR
    subgraph S["Sources brutes"]
        A["admissions.csv"]
        B["services.xlsx"]
        C["consultations.json"]
    end
    S --> N["Nettoyage<br/>clean.py"]
    N -->|lignes rejetées| Q[("Quarantaine<br/>+ rapport qualité")]
    N --> M["Modèle en étoile<br/>model.py"]
    M --> K{"Contrôles<br/>d'intégrité"}
    K --> P[("PostgreSQL<br/>clés + contraintes")]
    K --> BI["Power BI<br/>mesures DAX"]
    K --> F["Analyse + prévision<br/>analysis.py"]
```

Le principe de conception tient en une phrase : une ligne est soit **corrigée**, soit **gardée avec une valeur vide**, soit **rejetée en quarantaine avec son motif**, et chaque cas est compté dans le rapport qualité.

## Résultats (graine 42, données synthétiques)

| Source | Lignes brutes | Doublons | Rejetées | Propres |
|---|---:|---:|---:|---:|
| admissions | 30 694 | 602 | 380 | 29 712 |
| consultations | 49 423 | 730 | 0 | 48 693 |

| Ce que montrent les données | Valeur |
|---|---|
| Occupation des urgences (la plus élevée) | **86,7 %**, au-dessus du seuil de tension de 80 % |
| Saisonnalité | pic en décembre (indice 1,15), creux en septembre (0,89) |
| Prévision à 3 mois, erreur de backtest | **45** admissions/mois (3,6 %) contre 101 (8,2 %) pour la méthode naïve |

Détail dans [`reports/quality_report.md`](reports/quality_report.md) et [`reports/analyse.md`](reports/analyse.md). La saisonnalité est codée dans le générateur : elle valide la méthode, pas un phénomène réel.

## Aperçus

<table>
<tr>
<td width="33%"><a href="docs/img/02-consultations.png"><img src="docs/img/02-consultations.png" alt="Consultations"></a><br><sub><b>Consultations</b> : rendez-vous par statut, taux d'absence</sub></td>
<td width="33%"><a href="docs/img/03-qualite.png"><img src="docs/img/03-qualite.png" alt="Qualité des données"></a><br><sub><b>Qualité des données</b> : anomalies et traitement</sub></td>
<td width="33%"><a href="docs/img/04-prevision.png"><img src="docs/img/04-prevision.png" alt="Prévision"></a><br><sub><b>Prévision</b> : 3 mois, validée par backtest</sub></td>
</tr>
</table>

*Aperçus rendus avec matplotlib (`make figures`), avec les mêmes indicateurs que les mesures DAX. Le rapport Power BI (`.pbix`) se construit avec [`powerbi/GUIDE.md`](powerbi/GUIDE.md).*

## Lancer le projet

```bash
make install     # dépendances Python
make all         # génère les données, nettoie, analyse, lance les tests
make figures     # régénère les aperçus dans docs/img
```

Avec Docker : `make docker-build && make docker-run`. Sorties : `data/processed/*.csv`, `reports/quality_report.md`, `reports/analyse.md`.

### Base PostgreSQL

```bash
make db-up       # démarre PostgreSQL dans Docker
make db-load     # schéma (clés, contraintes) + chargement des 6 tables (client psql requis)
make db-check    # contrôles de cohérence SQL
make db-query    # 7 requêtes d'analyse
make db-down
```

Connexion par défaut : `postgresql://hkpi:hkpi@localhost:5432/hopital` (variable `DATABASE_URL`). La base impose elle-même les règles du nettoyage (sexe, statut, âge entre 0 et 110, sortie après l'entrée). Le job `postgres` de la CI la recrée de zéro à chaque push.

## Indicateurs

| Indicateur | Définition |
|---|---|
| Durée moyenne de séjour (DMS) | Moyenne de (date de sortie - date d'entrée) sur les séjours terminés |
| Taux d'occupation | Jours-lits occupés / (lits installés × jours du mois), en rapport de sommes |
| Part d'entrées par les urgences | Admissions via les urgences / admissions |
| Taux d'absence en consultation | Rendez-vous « absent » / rendez-vous total |

## Structure

```
src/hkpi/      generate.py · clean.py · model.py · quality.py · pipeline.py
               analysis.py · forecast.py · figures.py · sae.py
sql/           schema.sql · load.sql · checks.sql · analyses.sql
tests/         37 tests (nettoyage, intégrité, KPI, analyse, prévision, SAE)
powerbi/       guide (5 pages), mesures DAX
docs/          COMPRENDRE.md (choix techniques, questions d'entretien) · img/
data/external/ source publique SAE, optionnelle (à télécharger)
```

<details>
<summary><b>Choix techniques</b></summary>

| Choix | Raison |
|---|---|
| Format de date explicite par motif | `02/03/2024` est ambigu (2 mars ou 3 février) : on impose `jj/mm/aaaa` plutôt que de laisser pandas deviner |
| Quarantaine plutôt que suppression | Chaque ligne écartée est auditable et peut être renvoyée au système source |
| Taux en rapport de sommes | La moyenne de taux donne le même poids à un service de 12 lits et à un de 36 |
| Prévision saisonnière naïve | 24 mois ne suffisent pas à valider un modèle saisonnier complet ; on compare à une méthode naïve par backtest |
| `\copy` pour charger PostgreSQL | Aucune dépendance Python supplémentaire, utilisable en local, Docker ou CI |

Voir [`docs/COMPRENDRE.md`](docs/COMPRENDRE.md) pour le détail et les questions d'entretien.
</details>

## Limites assumées

- Premier mois sans taux d'occupation ; séjours sans date de sortie exclus de la DMS et de l'occupation.
- Un séjour d'un jour compte pour 1 jour-lit, ce qui surestime l'occupation des urgences.
- Données synthétiques : la saisonnalité vient du générateur. Prévision sur 24 mois seulement, donc méthode volontairement simple.
- Le schéma et les requêtes SQL ont été validés sur SQLite en local ; l'exécution sur PostgreSQL est celle du job `postgres` de la CI.

## Avancement

- [x] Pipeline de nettoyage et modèle en étoile, 3 sources
- [x] Base PostgreSQL : schéma, chargement, contrôles, requêtes, CI
- [x] Analyse de tendance et de saisonnalité, prévision avec backtest
- [x] Aperçus du tableau de bord
- [ ] Rapport Power BI (`.pbix`) : modèle, mesures DAX et guide fournis, à construire
- [ ] Source publique SAE (DREES) : code d'ingestion fourni, fichier à télécharger ([`data/external/README.md`](data/external/README.md))

## Stack

Python (pandas, NumPy, matplotlib, openpyxl) · pytest · PostgreSQL 16 · Docker Compose · GitHub Actions · Make · Power BI (DAX)
