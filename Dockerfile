FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src ./src
COPY tests ./tests

# Par défaut : génère les sources brutes puis exécute le pipeline.
CMD ["sh", "-c", "python -m hkpi.generate --out data/raw && python -m hkpi.pipeline --raw data/raw --out data/processed --reports reports"]
