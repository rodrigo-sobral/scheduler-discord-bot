#!/bin/bash
# Automatically format and lint Python code

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found."
    echo "Please run: bash scripts/setup.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if black is installed
python3 -c "import black" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  black not installed. Installing..."
    pip install black > /dev/null 2>&1
fi

# Check if flake8 is installed
python3 -c "import flake8" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  flake8 not installed. Installing..."
    pip install flake8 > /dev/null 2>&1
fi

echo "🎨 Formatting Python code with black..."
echo ""

# Run black to auto-format all Python files
black src/ --line-length=120 --quiet

echo "✅ Code formatted!"
echo ""
echo "🔍 Checking for remaining issues with flake8..."
echo ""

# Run flake8 on all Python files in src/
flake8 src/ \
    --count \
    --show-source \
    --statistics \
    --max-line-length=120 \
    --ignore=E501,W503,E203

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ All checks passed! Code is formatted and clean."
else
    echo "⚠️  Some issues remain. Review and fix manually if needed."
fi

exit $exit_code
