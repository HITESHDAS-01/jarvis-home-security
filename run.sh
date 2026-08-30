#!/bin/bash

echo "========================================"
echo "JARVIS Home Security System"
echo "========================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed"
    echo "Please install Python 3.8+"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "Starting JARVIS..."
echo ""
python main.py
