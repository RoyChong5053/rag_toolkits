#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "============================================"
echo "  RAG Toolkits - Setup"
echo "============================================"
echo ""

# Check Python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found. Please install Python 3.10+ first."
    exit 1
fi
echo "Python: $($PYTHON --version)"

# Create venv
if [ -d "venv" ]; then
    echo "venv/ already exists, recreating..."
    rm -rf venv
fi
echo "Creating virtual environment..."
$PYTHON -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create directory structure
mkdir -p input/raw input/clean input/photo output/rag output/ocr output/archive checkpoints intermediate logs

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Run:  ./run.sh"
echo "  Or:   source venv/bin/activate && python main.py"
echo ""
