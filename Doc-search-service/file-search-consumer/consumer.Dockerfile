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
    libpq-dev \
    libreoffice \
    libgl1 \
    libglib2.0-0 --fix-missing \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY consumer_requirements.txt /app/consumer_requirements.txt

COPY packages /app/packages
COPY core /app/core
COPY db /app/db
COPY event_driven /app/event_driven
COPY logger /app/logger
COPY schemas /app/schemas
COPY utils /app/utils

RUN pip install fast-inverted-index
RUN pip install -r /app/consumer_requirements.txt


RUN groupadd -r basicgroup && useradd -r -g basicgroup basicuser

RUN mkdir -p /home/basicuser/nltk_data/corpora/stopwords && \
    mkdir -p /home/basicuser/nltk_data/tokenizers/punkt && \
    mkdir -p /home/basicuser/nltk_data/tokenizers/punkt_tab && \
    chown -R basicuser:basicgroup /home/basicuser && \
    mkdir -p /app/temp /app/ameya-inverted-index && \
    chown -R basicuser:basicgroup /app

RUN python -c "import nltk; nltk.download('stopwords', download_dir='/home/basicuser/nltk_data')" && \
    python -c "import nltk; nltk.download('punkt', download_dir='/home/basicuser/nltk_data')" && \
    python -c "import nltk; nltk.download('punkt_tab', download_dir='/home/basicuser/nltk_data')"


RUN pip install awscli
RUN pip install --upgrade boto3

RUN chmod -R 770 /app/temp /app/ameya-inverted-index

USER basicuser

CMD ["sh", "-c", "python3 /app/event_driven/consumer.py"]

