#!/bin/bash

echo "Checking setup..."
echo ""

# Check Node.js. The fetch scripts rely on import.meta.main, which older 22.x
# releases lack, so they would silently do nothing.
NODE_RANGE='^22.18.0 || >=24.2.0'
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js $NODE_RANGE"
    exit 1
fi
if ! node -e '
const [major, minor] = process.versions.node.split(".").map(Number);
process.exit((major === 22 && minor >= 18) || (major === 24 && minor >= 2) || major >= 25 ? 0 : 1);
'; then
    echo "❌ Node.js $(node --version) is not supported. Please install Node.js $NODE_RANGE"
    exit 1
fi
echo "✓ Node.js $(node --version)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.11+"
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "❌ $(python3 --version 2>&1) is too old. Please install Python 3.11+"
    exit 1
fi
echo "✓ $(python3 --version 2>&1)"

# Check git. The drift pipeline reads its clone with GIT_NO_LAZY_FETCH, which
# older git ignores, so a pin missing from the clone would be downloaded
# instead of reported as invalid
GIT_MIN='2.44'
if ! command -v git &> /dev/null; then
    echo "❌ git not found. Please install git $GIT_MIN+"
    exit 1
fi
if ! git --version | awk -v min="$GIT_MIN" '{
    split($3, have, "."); split(min, need, ".")
    exit !(have[1] > need[1] || (have[1] == need[1] && have[2] >= need[2]))
}'; then
    echo "❌ $(git --version) is too old for the drift pipeline. Please install git $GIT_MIN+"
    exit 1
fi
echo "✓ $(git --version)"

# Check GITHUB_TOKEN, from the environment or from .env
if [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "✓ GITHUB_TOKEN set in the environment"
elif [ ! -f .env ]; then
    echo "❌ GITHUB_TOKEN is not set and .env was not found"
    echo "   Export GITHUB_TOKEN, or copy .env.example to .env and add your token"
    exit 1
elif ! grep -q '^GITHUB_TOKEN=.' .env || grep -q '^GITHUB_TOKEN=your_github_token_here' .env; then
    echo "❌ GITHUB_TOKEN not configured in .env"
    echo "   Edit .env and add your GitHub personal access token"
    exit 1
else
    echo "✓ GITHUB_TOKEN configured in .env"
fi

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
echo "✅ All checks passed! Run 'make help' to see available commands"
