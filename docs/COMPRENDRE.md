# Comprendre le projet (à lire avant un entretien)

## En une phrase

Trois exports de systèmes différents, pleins d'erreurs, sont nettoyés par des règles explicites et comptées, puis assemblés en un modèle en étoile qui alimente des indicateurs hospitaliers dans Power BI.

## Le parcours des données

1. **Génération** (`generate.py`) : fabrique les 3 sources avec des erreurs volontaires. C'est ce qui remplace les vraies données, qui seraient confidentielles. Graine fixe = mêmes données à chaque exécution.
2. **Nettoyage** (`clean.py`) : une règle = une fonction courte. Trois issues possibles pour une ligne : corrigée, gardée avec une valeur vide, ou rejetée en quarantaine avec son motif.
3. **Modélisation** (`model.py`) : dimensions (service, date), faits (admissions, consultations) et table mensuelle de KPI.
4. **Contrôles** (`pipeline.py`) : clés uniques, clés étrangères valides. Si un contrôle échoue, le pipeline s'arrête.
5. **Rapport qualité** (`quality.py`) : combien d'anomalies, de quel type, et ce qu'on en a fait.

## Choix techniques et pourquoi

| Choix | Raison |
|---|---|
| Format de date explicite par motif | `02/03/2024` est ambigu (2 mars ou 3 février). On impose `jj/mm/aaaa` plutôt que de laisser pandas deviner. |
| Quarantaine plutôt que suppression | On peut expliquer et auditer chaque ligne écartée, et la renvoyer au système source pour correction. |
| Date de sortie manquante : on garde la ligne | L'admission est réelle et compte dans les volumes ; seule la durée est inconnue. |
| Sortie avant entrée : on rejette | On ne sait pas quelle date est fausse, donc toute durée calculée serait fausse. |
| Schéma en étoile | Requêtes simples et rapides dans Power BI, mesures DAX lisibles, une dimension partagée entre plusieurs faits. |
| Table mensuelle précalculée | L'occupation (jours-lits répartis par mois) est plus fiable calculée une fois en Python qu'à chaque rafraîchissement en DAX. |
| Tests + CI + Docker | Montre qu'on sait livrer du code qui tourne partout et qui ne régresse pas. |

## Questions probables et pistes de réponse

**« Pourquoi des données synthétiques ? »** Les données de santé sont sensibles (RGPD, secret médical). Les données synthétiques permettent de montrer la méthode sans risque, et d'injecter des anomalies dont on connaît le nombre pour vérifier que le nettoyage les trouve.

**« Comment sais-tu que ton nettoyage est correct ? »** Les tests vérifient chaque règle sur des cas construits à la main, et la relation lignes brutes = doublons + rejetées + propres. Les contrôles d'intégrité bloquent le pipeline en cas d'erreur.

**« Qu'est-ce qui limite la fiabilité des KPI ? »** Premier mois sans occupation, séjours sans date de sortie exclus, séjour d'un jour compté pour 1 jour-lit. C'est documenté dans le README et le guide Power BI.

**« Qu'améliorerais-tu avec plus de temps ? »** Orchestration avec Airflow ou Dagster, chargement incrémental, base PostgreSQL à la place des CSV, tests de qualité avec Great Expectations ou dbt, alertes sur dérive de qualité.


## À faire toi-même pour bien le maîtriser (environ 2 h)

1. Lance `make all`, ouvre `reports/quality_report.md` et `reports/rejected_admissions.csv`.
2. Dans `clean.py`, lis `clean_admissions` ligne par ligne et explique chaque étape à voix haute.
3. Casse volontairement une règle (par exemple, retire le dédoublonnage), relance `make test` et observe quel test échoue.
4. Construis le dashboard en suivant `powerbi/GUIDE.md` et prends des captures d'écran.
