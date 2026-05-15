#!/bin/bash
# Automatically format and lint Python code using uv

# Check if .venv exists (uv creates this)
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found."
    echo "Please run: bash scripts/setup.sh"
    exit 1
fi

echo "🎨 Formatting Python code with ruff..."
echo ""

# Run ruff format to auto-format all Python files
uv run ruff format src/ --line-length=120

echo "✅ Code formatted!"
echo ""
echo "🔍 Checking for remaining issues with ruff..."
echo ""

# Run ruff check on all Python files
uv run ruff check src/ --line-length=120

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ All checks passed! Code is formatted and clean."
else
    echo "⚠️  Some issues remain. Review and fix manually if needed."
fi

exit $exit_code
