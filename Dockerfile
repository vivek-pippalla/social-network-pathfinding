# -------------------
# 1️⃣ Builder Stage
# -------------------
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------
# 2️⃣ Production Stage
# -------------------
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local

# Copy your application code
COPY src/ ./src/
COPY *.py ./

# Environment variables
ENV PYTHONPATH="/app/src:/app"
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=api_server.py
ENV HOST=0.0.0.0
ENV PORT=5000

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose Flask port
EXPOSE 5000

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start the app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "30", "api_server:create_app()"]
