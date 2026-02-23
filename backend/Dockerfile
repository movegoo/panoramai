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

# Copy MCP server package (from repo root via dockerContext)
COPY competitive-mcp/src/competitive_mcp /app/competitive_mcp

# Copy application code
COPY backend/ /app/

# Create cache directory
RUN mkdir -p /app/cache/datagouv

# Expose port (Railway sets PORT dynamically)
EXPOSE ${PORT:-8000}

# Run the application (PORT env var set by Railway/Render)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
