#!/bin/bash
# Run the Scheduler Bot with auto-restart on file changes using uv

# Check if .venv exists (uv creates this)
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found."
    echo "Please run: bash scripts/setup.sh"
    exit 1
fi

# Fix SSL certificate verification on macOS
export SSL_CERT_FILE=$(python3 -m certifi)

# Function to start the bot
start_bot() {
    echo "🚀 Starting Scheduler Bot..."
    uv run -m src &
    BOT_PID=$!
}

# Function to stop the bot
stop_bot() {
    if [ ! -z "$BOT_PID" ] && kill -0 $BOT_PID 2>/dev/null; then
        echo "🛑 Stopping bot (PID: $BOT_PID)..."
        kill $BOT_PID
        wait $BOT_PID 2>/dev/null
    fi
}

# Function to watch for file changes and restart
watch_and_restart() {
    # Watch src/ directory for changes with uv
    uv run watchmedo auto-restart \
        --directory=./src \
        --pattern="*.py" \
        --recursive \
        --signal SIGTERM \
        -- python -m src &
    WATCH_PID=$!
}

# Trap to handle script termination
cleanup() {
    echo ""
    echo "⏸️  Shutting down..."
    kill $WATCH_PID 2>/dev/null
    stop_bot
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start bot with auto-restart on changes
echo "👀 Watching for file changes in ./src..."
echo "ℹ️  Press Ctrl+C to stop"
echo ""

watch_and_restart
wait $WATCH_PID
