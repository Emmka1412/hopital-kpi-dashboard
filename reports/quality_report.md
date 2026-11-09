# Rapport qualité des données

Généré automatiquement par `python -m hkpi.pipeline`.

## Volumétrie par source

| Source | Lignes brutes | Doublons supprimés | Lignes rejetées | Lignes propres | Part conservée |
|---|---:|---:|---:|---:|---:|
| services | 9 | 0 | 1 | 8 | 88.9 % |
| admissions | 30 694 | 602 | 380 | 29 712 | 96.8 % |
| consultations | 49 423 | 730 | 0 | 48 693 | 98.5 % |

## Anomalies détectées et traitement

| Source | Règle | Nombre | % des lignes brutes | Traitement |
|---|---|---:|---:|---|
| services | ligne_hors_service (total, vide) | 1 | 11.11 % | ignorée |
| admissions | doublon_id_adm | 602 | 1.96 % | supprimé (première occurrence conservée) |
| admissions | date_sortie_manquante | 905 | 2.95 % | conservé (exclu des durées de séjour) |
| admissions | date_sortie_avant_entree | 314 | 1.02 % | rejeté (quarantaine) |
| admissions | service_inconnu | 66 | 0.22 % | rejeté (quarantaine) |
| admissions | age_manquant | 301 | 0.98 % | conservé (âge vide) |
| admissions | age_aberrant (hors 0-110) | 151 | 0.49 % | valeur vidée |
| consultations | doublon_rdv_id | 730 | 1.48 % | supprimé (première occurrence conservée) |
| consultations | duree_honoree_manquante_ou_negative | 812 | 1.64 % | valeur vidée |

## Lecture

- **Corrigé** : normalisation (formats de dates, libellés de services, identifiants patients, sexe, modes d'entrée/sortie).
- **Conservé avec valeur vide** : l'information manquante ou aberrante est vidée, la ligne reste exploitable pour les autres indicateurs.
- **Rejeté** : la ligne ne peut pas être utilisée de façon fiable ; elle est écrite dans `reports/rejected_*.csv` avec son motif.
- Contrôle de cohérence : lignes brutes = doublons + rejetées + propres (vérifié par les tests).
