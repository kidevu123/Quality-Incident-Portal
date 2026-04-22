# Nexus Resolve — production-style app image
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=config.settings.production

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
