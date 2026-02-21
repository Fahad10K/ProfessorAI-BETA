# ProfessorAI Production Dockerfile
# Multi-stage build for optimized image size and security

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Stage 2: Runtime - Minimal production image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security
RUN useradd -m -u 1000 profai && \
    mkdir -p /app && \
    chown -R profai:profai /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=profai:profai . .

# Create necessary directories with proper permissions
RUN mkdir -p \
    data/documents \
    data/vectorstore \
    data/courses \
    data/quizzes \
    data/quiz_answers \
    && chown -R profai:profai data

# Switch to non-root user
USER profai

# Expose ports
# 5001 - FastAPI REST API
# 8765 - WebSocket Server
EXPOSE 5001 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

# Start the application
CMD ["python", "-u", "run_profai_websocket.py"]
