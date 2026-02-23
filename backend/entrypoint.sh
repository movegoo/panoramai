#!/bin/sh
set -e

# Sync GeoJSON cache from S3 if bucket is configured
if [ -n "$S3_CACHE_BUCKET" ]; then
  echo "Syncing GeoJSON cache from s3://${S3_CACHE_BUCKET}/datagouv..."
  aws s3 sync "s3://${S3_CACHE_BUCKET}/datagouv" /app/cache/datagouv --quiet || echo "Warning: S3 sync failed, continuing without cache"
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
