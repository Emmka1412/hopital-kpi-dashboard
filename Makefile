PY ?= python3
export PYTHONPATH := src

.PHONY: install data pipeline test all docker-build docker-run clean

install:            ## installe les dépendances
	$(PY) -m pip install -r requirements.txt

data:               ## génère les sources brutes synthétiques (graine fixe)
	$(PY) -m hkpi.generate --out data/raw

pipeline:           ## nettoie, consolide et produit les tables Power BI + rapport qualité
	$(PY) -m hkpi.pipeline --raw data/raw --out data/processed --reports reports

test:               ## lance les tests automatisés
	$(PY) -m pytest -q

all: data pipeline test   ## tout reconstruire en une commande

docker-build:
	docker build -t hopital-kpi-dashboard .

docker-run:         ## exécute le pipeline dans un conteneur
	docker run --rm -v "$(PWD)/data:/app/data" -v "$(PWD)/reports:/app/reports" hopital-kpi-dashboard

clean:
	rm -rf data/raw/*.csv data/raw/*.json data/raw/*.xlsx data/processed/*.csv reports/rejected_*.csv .pytest_cache
