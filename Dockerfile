FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=10000
ENV PYTHONUNBUFFERED=1
ENV WEB_CONCURRENCY=1

# Start the application with optimized Gunicorn settings
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 2 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 50 \
    --max-requests-jitter 5 \
    --log-level debug \
    app:app 