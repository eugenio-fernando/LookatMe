#!/bin/sh
set -e

# Resolve database path: use Fly.io persistent volume if mounted, else local fallback
if [ -d /data ]; then
  export DATABASE_URL="file:/data/lookatme.db"
else
  export DATABASE_URL="file:./lookatme.db"
fi
echo "DB: DATABASE_URL=$DATABASE_URL"

echo "Running prisma db push..."
prisma db push --skip-generate

echo "Starting gunicorn..."
exec gunicorn run:app --bind 0.0.0.0:8080 -k gthread --threads 4 -w 1
