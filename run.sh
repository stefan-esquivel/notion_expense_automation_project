#!/bin/bash

# Notion Expense Automation - Quick Start Script

echo "🚀 Starting Notion Expense Automation..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and configure it"
    echo "Run: cp .env.example .env"
    exit 1
fi

# Run the application
python src/main.py

# Deactivate virtual environment
deactivate

# Made with Bob
