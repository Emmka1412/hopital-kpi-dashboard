# Analyse des KPI : tendance, saisonnalité et prévision

Généré par `python -m hkpi.analysis` sur 24 mois (01/2024 à 12/2025). Données synthétiques : la saisonnalité décrite ci-dessous est celle codée dans le générateur ; ce rapport valide la méthode, pas un phénomène hospitalier réel.

## 1. Lecture en cinq points

1. **Volume et tendance.** Les 12 derniers mois comptent 1,6 % d'admissions de plus que les 12 précédents. Une fois la saisonnalité retirée, la tendance est de 1,2 % par an : l'activité est stable sur la période.
2. **Saisonnalité.** Le pic est en décembre (indice 1,15) et le creux en septembre (indice 0,89) : l'activité du mois le plus chargé est 1,29 fois celle du mois le plus calme.
3. **Pression sur les lits.** Urgences a l'occupation la plus élevée (86,7 %), au-dessus du seuil de tension de 80 %. Les séjours d'un jour comptent pour 1 jour-lit, ce qui gonfle l'occupation des services à séjours très courts.
4. **Consultations.** Le taux d'absence global est de 10,1 %, de 9,7 % (Radiologie) à 10,4 % (Pédiatrie) selon les services.
5. **Prévision.** Pour les 3 prochains mois, la méthode saisonnière prévoit 1 442 (01/2026), 1 306 (02/2026), 1 392 (03/2026) admissions, avec une erreur attendue d'environ ± 45 admissions par mois.

## 2. Indice saisonnier par mois civil

| Mois | Indice (1,00 = mois moyen) |
|---|---:|
| janvier | 1,124 |
| février | 1,038 |
| mars | 1,099 |
| avril | 1,003 |
| mai | 0,958 |
| juin | 0,901 |
| juillet | 0,902 |
| août | 0,901 |
| septembre | 0,895 |
| octobre | 1,015 |
| novembre | 1,014 |
| décembre | 1,150 |

## 3. Occupation par service

| Service | Taux d'occupation | Lecture |
|---|---:|---|
| Urgences | 86,7 % | tension |
| Maternité | 76,4 % | normal |
| Médecine interne | 75,5 % | normal |
| Pédiatrie | 74,2 % | normal |
| Chirurgie | 73,9 % | normal |
| Cardiologie | 73,7 % | normal |
| Réanimation | 70,2 % | normal |

## 4. Prévision : méthode et validation

Avec 24 mois d'historique, un modèle saisonnier complet (Holt-Winters, SARIMA) n'est pas fiable : il faut au moins deux cycles complets pour séparer la tendance de la saisonnalité et en valider l'estimation. On compare donc deux méthodes expliquables en une phrase, par un backtest à origine glissante (7 origines, horizon 3 mois).

| Méthode | Erreur absolue moyenne (admissions/mois) | En % du niveau moyen |
|---|---:|---:|
| Naïve (répète le dernier mois) | 101,2 | 8,2 % |
| Saisonnière naïve (mêmes mois de l'an passé) | 45,0 | 3,6 % |

La prévision publiée applique en plus la croissance des 12 derniers mois (1,6 %) aux mêmes mois de l'année précédente.

## 5. Limites

- Données synthétiques : la saisonnalité vient du générateur, donc la validation prouve le code et la méthode.
- Deux années seulement : l'indice saisonnier est estimé sur les mêmes données que celles qu'il sert à désaisonnaliser.
- La prévision ne tient pas compte d'événements exceptionnels (épidémie, fermeture de service).
- Premier mois sans taux d'occupation, séjours sans date de sortie exclus des durées : voir le rapport qualité.
