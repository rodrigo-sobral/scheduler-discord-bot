#!/bin/bash
# Setup script for Scheduler Bot using uv
# This script sets up the development environment

set -e
PATH=/usr/local/bin:$PATH

echo "📅 Scheduler Bot Setup"
echo "===================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create and sync virtual environment with uv
echo "Setting up virtual environment and dependencies..."
uv sync --dev

# Check if Prisma needs setup
if [ ! -f "db/database.db" ]; then
    echo "Setting up Prisma..."
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo "⚠️  npm not found. Please install Node.js and npm, then run:"
        echo "   npx prisma generate --schema=prisma/schema.prisma"
    else
        echo "Generating Prisma client..."
        uv run prisma generate --schema=prisma/schema.prisma
    fi
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your BOT_TOKEN"
else
    echo "✅ .env file found"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Discord Bot Token"
echo "2. Run: uv run python -m src"
echo ""
