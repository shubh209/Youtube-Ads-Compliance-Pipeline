FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# ffmpeg is required by yt-dlp to merge video+audio streams
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first (better layer caching)
# Docker caches this layer — only re-runs if pyproject.toml changes
COPY pyproject.toml .
COPY uv.lock .

# Install dependencies
RUN uv pip install --system .

# Copy source code
COPY . .

EXPOSE 8000

# timeout-keep-alive 300 = 5 minutes
# Azure Video Indexer takes 2-5 min to process — without this
# uvicorn drops the connection before the pipeline finishes
CMD ["uvicorn", "backend.src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]