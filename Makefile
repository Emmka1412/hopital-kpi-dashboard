PY ?= python3
export PYTHONPATH := src
DATABASE_URL ?= postgresql://hkpi:hkpi@localhost:5432/hopital

.PHONY: install data pipeline analysis sae figures test all docker-build docker-run db-up db-load db-check db-query db-down clean

install:            ## installe les dépendances
	$(PY) -m pip install -r requirements.txt

data:               ## génère les sources brutes synthétiques (graine fixe)
	$(PY) -m hkpi.generate --out data/raw

pipeline:           ## nettoie, consolide et produit les tables Power BI + rapport qualité
	$(PY) -m hkpi.pipeline --raw data/raw --out data/processed --reports reports

analysis:           ## prévision à 3 mois + rapport d'analyse (reports/analyse.md)
	$(PY) -m hkpi.analysis --processed data/processed --reports reports

sae:                ## (optionnel) ingère le fichier SAE de la DREES placé dans data/external/
	$(PY) -m hkpi.sae --in data/external/lits_soins_critiques.csv

figures:            ## aperçus du tableau de bord en PNG (docs/img), rendus avec matplotlib
	$(PY) -m hkpi.figures --processed data/processed --reports reports --out docs/img

test:               ## lance les tests automatisés
	$(PY) -m pytest -q

all: data pipeline analysis test   ## tout reconstruire en une commande

db-up:              ## démarre PostgreSQL (Docker) et attend qu'il soit prêt
	docker compose up -d --wait db

db-load:            ## crée le schéma et charge les tables (nécessite le client psql)
	psql "$(DATABASE_URL)" -v ON_ERROR_STOP=1 -f sql/schema.sql -f sql/load.sql

db-check:           ## contrôles de cohérence SQL
	psql "$(DATABASE_URL)" -v ON_ERROR_STOP=1 -f sql/checks.sql

db-query:           ## exécute les requêtes d'analyse
	psql "$(DATABASE_URL)" -v ON_ERROR_STOP=1 -f sql/analyses.sql

db-down:            ## arrête PostgreSQL
	docker compose down

docker-build:
	docker build -t hopital-kpi-dashboard .

docker-run:         ## exécute le pipeline dans un conteneur
	docker run --rm -v "$(PWD)/data:/app/data" -v "$(PWD)/reports:/app/reports" hopital-kpi-dashboard

clean:
	rm -rf data/raw/*.csv data/raw/*.json data/raw/*.xlsx data/processed/*.csv reports/rejected_*.csv .pytest_cache
