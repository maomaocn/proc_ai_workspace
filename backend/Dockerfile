FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=5

WORKDIR /app

COPY pyproject.toml ./
COPY app/__init__.py ./app/__init__.py

RUN pip install --no-cache-dir ".[dev]" \
    && rm -rf /app/app

COPY alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY tests ./tests
COPY docker-entrypoint.sh ./

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
