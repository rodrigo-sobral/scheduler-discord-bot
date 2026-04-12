#!/bin/bash
# Setup script for Scheduler Bot
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

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r config/requirements.txt --upgrade

# Check if Prisma needs setup
if [ ! -f "db/database.db" ]; then
    echo "Setting up Prisma..."
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo "⚠️  npm not found. Please install Node.js and npm, then run:"
        echo "   npx prisma generate --schema=prisma/schema.prisma"
    else
        echo "Generating Prisma client..."
        python -m prisma generate --schema=prisma/schema.prisma
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
echo "2. Run: python3 -m src"
echo ""
echo "For help, run: python3 -m src"
echo ""
