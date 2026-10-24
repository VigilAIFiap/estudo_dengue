# API analítica (FastAPI). Build a partir da raiz do projeto.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-api.txt ./
RUN pip install --prefer-binary -r requirements-api.txt

COPY api ./api
COPY src ./src
COPY deploy ./deploy

EXPOSE 8000
CMD ["python", "deploy/entrypoint.py"]
