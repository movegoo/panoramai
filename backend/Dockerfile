FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including AWS CLI for S3 sync)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    unzip \
    && curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip -q awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && apt-get purge -y unzip \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (includes competitive_mcp/ package)
COPY . .

# Create cache directory and non-root user
RUN mkdir -p /app/cache/datagouv && \
    useradd -r -s /bin/false -d /app appuser && \
    chown -R appuser:appuser /app

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Run as non-root
USER appuser

# Expose port
EXPOSE ${PORT:-8000}

# Use entrypoint script (S3 sync + uvicorn)
ENTRYPOINT ["/app/entrypoint.sh"]
