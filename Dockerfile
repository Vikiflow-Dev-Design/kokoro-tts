FROM python:3.11-slim

# Install system audio and phonemizer dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set Python and HuggingFace environment variables
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf_cache

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY kokoro_server.py .
COPY kokoro_ui ./kokoro_ui

# Expose port for Coolify / Docker
EXPOSE 5050

# Run with Gunicorn (1 worker + 4 threads to keep PyTorch model in shared memory and avoid high RAM usage)
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5050", "--timeout", "300", "kokoro_server:app"]
