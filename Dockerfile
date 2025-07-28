# Use official slim Python base for AMD64 architecture
FROM --platform=linux/amd64 python:3.10-slim

# Set working directory in the container
WORKDIR /app

# Install system dependencies for PDF parsing and font rendering
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the container
COPY . .

# Pre-create model directory (used for caching sentence-transformers)
RUN mkdir -p /app/models

# Entry point for Adobe Round 1B
CMD ["python", "main_round1b.py"]
