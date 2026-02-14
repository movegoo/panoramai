FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p /app/cache/datagouv

# Railway passes env vars as build args for Docker builds
# Capture them so they're available at runtime
ARG ANTHROPIC_API_KEY
ARG CLAUDE_KEY
ARG GEMINI_API_KEY
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ENV CLAUDE_KEY=${CLAUDE_KEY}
ENV GEMINI_API_KEY=${GEMINI_API_KEY}

# Expose port (Railway sets PORT dynamically)
EXPOSE ${PORT:-8000}

# Run the application (PORT env var set by Railway/Render)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
