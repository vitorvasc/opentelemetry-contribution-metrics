#!/bin/bash

echo "Checking setup..."
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi
echo "✓ Node.js $(node --version)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.8+"
    exit 1
fi
echo "✓ Python $(python3 --version 2>&1)"

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example to .env"
    exit 1
fi
echo "✓ .env file exists"

# Check GITHUB_TOKEN in .env
if ! grep -q "GITHUB_TOKEN=" .env || grep -q "GITHUB_TOKEN=your_github_token_here" .env; then
    echo "❌ GITHUB_TOKEN not configured in .env"
    echo "   Edit .env and add your GitHub personal access token"
    exit 1
fi
echo "✓ GITHUB_TOKEN configured"

# Check npm packages
if [ ! -d node_modules ]; then
    echo "⚠️  node_modules not found. Run: npm install"
    exit 1
fi
echo "✓ Node.js dependencies installed"

# Check Python packages
if ! python3 -c "import pandas, matplotlib, yaml" &> /dev/null; then
    echo "⚠️  Python dependencies missing. Run: pip install -r requirements.txt"
    exit 1
fi
echo "✓ Python dependencies installed"

# Check data directory
if [ ! -d data ]; then
    echo "⚠️  data/ directory not found. Creating..."
    mkdir -p data
fi
echo "✓ data/ directory exists"

echo ""
echo "✅ All checks passed! Ready to run 'make all'"
