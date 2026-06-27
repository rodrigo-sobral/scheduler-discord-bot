# Multi-stage build for Discord Scheduler Bot

# ─────────────────────────────────────────
# Stage 1: Builder
# ─────────────────────────────────────────
FROM python:3.12-alpine AS builder

WORKDIR /app

# Install build + runtime deps for prisma (needs node for generate)
RUN apk add --no-cache build-base libffi-dev openssl-dev openssl nodejs npm

# Install uv
RUN pip install --no-cache-dir uv

# Set env so venv is active for all subsequent RUN steps
ENV PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    VIRTUAL_ENV=/app/.venv

# Copy only dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./
COPY prisma ./prisma

# Install dependencies into /app/.venv
RUN uv sync --frozen --no-dev --no-editable --no-install-project --no-cache

# Generate Prisma client (writes to .venv AND /root/.cache/prisma-python)
RUN prisma generate --schema=/app/prisma/schema.prisma

# ─────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────
FROM python:3.12-alpine

LABEL maintainer="Scheduler Bot"
LABEL description="Discord Scheduler Bot - Schedule messages for later delivery"

WORKDIR /app

# Create non-root user
RUN addgroup -g 1000 scheduler && adduser -D -u 1000 -G scheduler scheduler

# Install runtime dependencies (no build tools, no node)
RUN apk add --no-cache ca-certificates libffi openssl procps

# Copy venv from builder
COPY --from=builder --chown=scheduler:scheduler /app/.venv /app/.venv

# Copy application source and assets
COPY --chown=scheduler:scheduler src /app/src
COPY --chown=scheduler:scheduler assets /app/assets

# Setup logs directory
RUN mkdir -p /app/logs && chown -R scheduler:scheduler /app

# Activate venv and point Prisma cache to the non-root user's home
ENV PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    VIRTUAL_ENV=/app/.venv

# Change to non-root user
USER scheduler

# Health check - verify bot process is actually running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "python -m src.__main__" > /dev/null || exit 1

# Run the bot
CMD ["python", "-m", "src.__main__"]
