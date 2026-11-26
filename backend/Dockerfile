FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

EXPOSE 8000
# Jeden worker: współdzielona przeglądarka Chromium do generowania PDF
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
