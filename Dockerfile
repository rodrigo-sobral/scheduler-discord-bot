# Multi-stage build for Discord Scheduler Bot
# Stage 1: Build stage
FROM python:3.14-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache build-base libffi-dev openssl-dev

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./

# Sync dependencies (--no-install-project since source isn't present in builder)
RUN uv sync --frozen --no-dev --no-editable --no-install-project --no-cache

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
    libffi \
    openssl \
    procps

# Copy virtual environment from builder
COPY --from=builder --chown=scheduler:scheduler /app/.venv /app/.venv

# Copy application code
COPY --chown=scheduler:scheduler src /app/src
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

# Health check - verify bot process is actually running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "python -m src.__main__" > /dev/null || exit 1

# Run the bot
CMD ["python", "-m", "src.__main__"]
