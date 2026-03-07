#!/bin/sh
set -e

echo "Running prisma db push..."
prisma db push --skip-generate

echo "Starting gunicorn..."
exec gunicorn run:app --bind 0.0.0.0:8080 -k gthread --threads 4 -w 1
