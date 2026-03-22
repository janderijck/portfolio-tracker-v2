# Python backend Dockerfile for Portfolio Tracker
# Multi-stage build: build deps in builder, copy only runtime to final image

# =============================================================================
# Stage 1: Builder - install system deps and compile Python packages
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (gcc needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies into a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Runtime - minimal image without build tools
# =============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/portfolio.db
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

WORKDIR /app

# Copy virtual env from builder (no gcc/build tools in final image)
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create data directory and set permissions
RUN mkdir -p /data && chown -R appuser:appgroup /data /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
