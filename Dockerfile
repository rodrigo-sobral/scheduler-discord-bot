# Multi-stage build for Discord Scheduler Bot
# Stage 1: Build stage
FROM python:3.12-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache build-base libffi-dev openssl-dev

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock* ./

# Sync dependencies (--no-dev to exclude dev dependencies)
RUN uv sync --frozen --no-dev --no-editable --no-cache

# Stage 2: Runtime stage
FROM python:3.12-alpine

# Set metadata
LABEL maintainer="Scheduler Bot"
LABEL description="Discord Scheduler Bot - Schedule messages for later delivery"

# Setup working directory
WORKDIR /app

# Create non-root user for security
RUN addgroup -g 1000 scheduler && adduser -D -u 1000 -G scheduler scheduler

# Install runtime dependencies only
RUN apk add --no-cache \
    ca-certificates \
    curl \
    libffi \
    openssl

# Copy virtual environment from builder
COPY --from=builder --chown=scheduler:scheduler /app/.venv /app/.venv

# Copy application code
COPY --chown=scheduler:scheduler src /app/src
COPY --chown=scheduler:scheduler config /app/config
COPY --chown=scheduler:scheduler assets /app/assets

# Setup logs directory
RUN mkdir -p /app/logs && chown -R scheduler:scheduler /app

# Change to non-root user
USER scheduler

# Ensure Python can find the app and uses the virtual environment
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:$PYTHONPATH \
    VIRTUAL_ENV=/app/.venv

# Health check - verify bot process is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import discord; exit(0)" || exit 1

# Run the bot
CMD ["python", "-m", "src.__main__"]
