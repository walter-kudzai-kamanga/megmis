FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 megmis
COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY data ./data
COPY src ./src
RUN pip install --no-cache-dir . \
 && chmod +x /app/scripts/entrypoint.sh /app/scripts/download_osm_extract.sh

FROM base AS prod
USER megmis
EXPOSE 8000
# Render/Fly set PORT; local/compose default 8000
CMD ["sh", "-c", "uvicorn megmis.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
