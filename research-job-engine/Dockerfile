FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install ".[dev]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
COPY sources.example.json ./

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# --proxy-headers: trust X-Forwarded-* from the reverse proxy (Caddy) for correct client info.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
