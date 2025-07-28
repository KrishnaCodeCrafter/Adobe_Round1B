FROM python:3.9-slim-buster AS builder
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libharfbuzz-dev \
    libfreetype6-dev \
    libfontconfig1 \
    libjpeg-dev \
    zlib1g-dev \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/models/all-MiniLM-L6-v2 && \
    python -c "from sentence_transformers import SentenceTransformer; model_name='all-MiniLM-L6-v2'; model = SentenceTransformer(model_name); model.save_pretrained(f'/app/models/{model_name}')"

COPY main_round1b.py .
COPY pdf_parser.py .

RUN mkdir -p input output

CMD ["python", "main_round1b.py"]