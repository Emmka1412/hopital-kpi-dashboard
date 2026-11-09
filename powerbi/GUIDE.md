# Guide Power BI (environ 1 h 30)

Le fichier `.pbix` n'est pas fourni : il se construit dans **Power BI Desktop** (Windows) à partir des tables prêtes à l'emploi dans `data/processed/`. Ce guide donne le modèle, les mesures et la disposition des pages. Construire le rapport toi-même est ce qui te permettra de le défendre en entretien.

## 1. Importer les données

1. Lance le pipeline : `make all`.
2. Power BI Desktop > **Obtenir les données > Texte/CSV**, puis charge les 5 fichiers de `data/processed/` :
   `dim_service`, `dim_date`, `fact_admission`, `fact_consultation`, `kpi_monthly_service`.
3. Dans **Transformer les données**, si des décimales (0.7736) apparaissent comme du texte ou des dates :
   colonne > **Modifier le type > Utiliser les paramètres régionaux... > Anglais (États-Unis)**.
4. Vérifie les types : colonnes de dates en *Date*, `taux_*` en *Nombre décimal*.

## 2. Modèle de données (schéma en étoile)

```
                     dim_date
                    (date, annee, mois ...)
                  1 /   |  1 \   \ 1
                   /    |      \   \
      fact_admission  fact_consultation  kpi_monthly_service
        (date_entree)    (date_rdv)        (mois_debut)
                   \     |      /
                    \    |     /
                   * \   |    / *
                     dim_service
                    (code_service)
```

Relations à créer (cardinalité un-à-plusieurs, filtre dans un seul sens, de la dimension vers le fait) :

| De (1) | Vers (*) |
|---|---|
| `dim_date[date]` | `fact_admission[date_entree]` |
| `dim_date[date]` | `fact_consultation[date_rdv]` |
| `dim_date[date]` | `kpi_monthly_service[mois_debut]` (relation à laisser inactive si Power BI signale une ambiguïté) |
| `dim_service[code_service]` | `fact_admission[service_code]` |
| `dim_service[code_service]` | `fact_consultation[service_code]` |
| `dim_service[code_service]` | `kpi_monthly_service[service_code]` |

Ensuite : sélectionne `dim_date` > **Outils de table > Marquer comme table de dates** (colonne `date`). C'est nécessaire pour `SAMEPERIODLASTYEAR`.

Astuce : trie `dim_date[mois_libelle]` par `dim_date[mois]` pour avoir janvier à décembre dans l'ordre.

## 3. Mesures

Crée une table vide `_Mesures` (Saisir des données) et colle les mesures de `measures.dax` une par une.

## 4. Pages du rapport

**Page 1 : Vue d'ensemble de l'activité**

| Zone | Visuel | Champs |
|---|---|---|
| Haut | 4 cartes | `Admissions`, `DMS (jours)`, `Taux d'occupation`, `Taux d'absence` |
| Milieu gauche | Courbe | Axe `dim_date[annee_mois]`, valeurs `Admissions` et `Admissions N-1` |
| Milieu droite | Barres horizontales | Axe `dim_service[libelle]`, valeurs `Admissions` |
| Bas | Matrice | Lignes `dim_service[libelle]`, valeurs `DMS (jours)`, `Taux d'occupation` |
| Côté | Segments (slicers) | `dim_date[annee]`, `dim_service[pole]` |

**Page 2 : Consultations**

- Histogramme empilé : `Rendez-vous` par mois, légende `fact_consultation[statut]`.
- Barres : `Taux d'absence` par service.
- Carte : `Durée moyenne de consultation (min)`.
- Segment : `dim_service[libelle]`.

**Page 3 : Qualité des données** (montre ton travail d'amont)

- Table construite à la main ou importée depuis `reports/anomalies.csv` : règle, nombre, traitement.
- Carte : lignes brutes vs lignes propres (valeurs du `quality_report.md`).

## 5. Finitions qui font la différence

- Mise en forme conditionnelle de la carte `Taux d'occupation` avec la mesure `Alerte occupation`.
- Infobulles de page personnalisées (survol d'un service > détail mensuel).
- Un titre explicite par visuel, une palette sobre, alignement soigné.
- Capture d'écran de chaque page, à enregistrer dans `docs/img/` puis à ajouter au README.

## 6. Limites à connaître (et à dire en entretien)

- Le **premier mois** n'a pas de taux d'occupation : les séjours antérieurs à la période d'export ne sont pas dans les données (censure à gauche).
- Les séjours **sans date de sortie** sont exclus de la DMS et de l'occupation.
- Un séjour d'une journée compte pour **1 jour-lit** ; cela gonfle l'occupation des urgences (séjours très courts).
- Les données sont **synthétiques** : les chiffres illustrent la méthode, pas une réalité hospitalière.
