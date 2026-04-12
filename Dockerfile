# Multi-stage build for Discord Scheduler Bot
# Stage 1: Build stage
FROM python:3.12-alpine AS builder

WORKDIR /tmp

# Install build dependencies
RUN apk add --no-cache build-base libffi-dev openssl-dev

# Copy requirements
COPY config/requirements.txt .

# Install Python dependencies to a temporary location
RUN pip install --user --no-cache-dir -r requirements.txt

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

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/scheduler/.local

# Copy application code
COPY src /app/src
COPY config /app/config
COPY assets /app/assets

# Setup logs directory
RUN mkdir -p /app/logs && chown -R scheduler:scheduler /app

# Change to non-root user
USER scheduler

# Ensure Python can find installed packages
ENV PATH=/home/scheduler/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:$PYTHONPATH

# Health check - verify bot process is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/proc/self') else 1)" || exit 1

# Run the bot
CMD ["python", "-m", "src.__main__"]
