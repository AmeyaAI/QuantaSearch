FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    NLTK_DATA="/home/basicuser/nltk_data"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    build-essential \
    gcc \
    g++ \
    libpq-dev --fix-missing\
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY core /app/core
COPY db /app/db
COPY event_driven /app/event_driven
COPY logger /app/logger
COPY main /app/main
COPY router /app/router
COPY schemas /app/schemas
COPY utils /app/utils

RUN pip install fast-inverted-index
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r basicgroup && \
    useradd -r -g basicgroup -d /home/basicuser -s /usr/sbin/nologin basicuser && \
    mkdir -p /home/basicuser && \
    mkdir -p /home/basicuser/nltk_data/corpora/stopwords && \
    mkdir -p /home/basicuser/nltk_data/tokenizers/punkt && \
    mkdir -p /home/basicuser/nltk_data/tokenizers/punkt_tab && \
    mkdir -p /app/temp /app/ameya-inverted-index && \
    chown -R basicuser:basicgroup /home/basicuser && \
    chown -R basicuser:basicgroup /app

RUN python -c "import nltk; nltk.download('stopwords', download_dir='/home/basicuser/nltk_data')" && \
    python -c "import nltk; nltk.download('punkt', download_dir='/home/basicuser/nltk_data')" && \
    python -c "import nltk; nltk.download('punkt_tab', download_dir='/home/basicuser/nltk_data')"

USER basicuser

EXPOSE 4444

CMD ["uvicorn", "main.api:app", "--host", "0.0.0.0", "--port", "4444"]