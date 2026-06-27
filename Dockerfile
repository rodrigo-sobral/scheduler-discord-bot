FROM python:3.12-alpine

LABEL maintainer="Scheduler Bot"
LABEL description="Discord Scheduler Bot - Schedule messages for later delivery"

WORKDIR /app

# Install all deps (build tools + node needed for prisma generate)
RUN apk add --no-cache build-base libffi-dev openssl-dev openssl nodejs npm ca-certificates procps

# Install uv
RUN pip install --no-cache-dir uv

# Create non-root user
RUN addgroup -g 1000 scheduler && adduser -D -u 1000 -G scheduler scheduler

ENV PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    VIRTUAL_ENV=/app/.venv \
    PRISMA_BINARY_CACHE_DIR=/app/.prisma-cache

COPY pyproject.toml uv.lock README.md ./
COPY prisma ./prisma
COPY src ./src
COPY assets ./assets

# Install dependencies and generate Prisma client
RUN uv sync --frozen --no-dev --no-editable --no-cache && \
    prisma generate --schema=/app/prisma/schema.prisma

# Setup logs directory and fix ownership (including prisma cache written as root)
RUN mkdir -p /app/logs && \
    chown -R scheduler:scheduler /app

USER scheduler

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "python -m src.__main__" > /dev/null || exit 1

CMD ["python", "-m", "src.__main__"]