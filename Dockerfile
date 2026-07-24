# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment
ENV PYTHONUNBUFFERED=1
ENV DISCORD_TOKEN=""
ENV DATABASE_PATH=/app/data/data.db

# Run bot
CMD ["python", "bot.py"]
