FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install hatchling (build backend for competitive-mcp)
RUN pip install --no-cache-dir hatchling

# Copy and install competitive-mcp package
COPY competitive-mcp /tmp/competitive-mcp
RUN pip install --no-cache-dir /tmp/competitive-mcp && rm -rf /tmp/competitive-mcp

# Copy application code
COPY backend/ .

# Create cache directory
RUN mkdir -p /app/cache/datagouv

# Expose port (Railway sets PORT dynamically)
EXPOSE ${PORT:-8000}

# Run the application (PORT env var set by Railway/Render)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
