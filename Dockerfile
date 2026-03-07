FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by Prisma
RUN apt-get update && apt-get install -y \
    curl \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .

# generate prisma client (schema compilation only — no DB connection needed)
RUN prisma generate

# ensure the volume mount point exists
RUN mkdir -p /data

EXPOSE 8080

# entrypoint runs prisma db push at startup (after volume is mounted), then gunicorn
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]