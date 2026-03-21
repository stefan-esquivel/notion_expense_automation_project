#!/bin/bash

# Notion Expense Automation - Quick Start Script
# Usage: ./run.sh [env]
#   ./run.sh       - Run with local environment (.env)
#   ./run.sh qa    - Run with QA environment (.env.qa)
#   ./run.sh prod  - Run with production environment (.env.prod)

ENV=${1:-local}

if [ "$ENV" = "prod" ]; then
    echo "🚀 Starting Notion Expense Automation (PRODUCTION)..."
    echo "⚠️  WARNING: Using REAL databases with REAL data!"
elif [ "$ENV" = "qa" ]; then
    echo "🧪 Starting Notion Expense Automation (QA)..."
else
    echo "🚀 Starting Notion Expense Automation (LOCAL)..."
fi
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if appropriate .env file exists
if [ "$ENV" = "qa" ]; then
    ENV_FILE=".env.qa"
elif [ "$ENV" = "prod" ]; then
    ENV_FILE=".env.prod"
else
    ENV_FILE=".env"
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ $ENV_FILE file not found!"
    echo "Please create $ENV_FILE based on .env.example"
    exit 1
fi

# Run the application with environment variable
if [ "$ENV" != "local" ]; then
    APP_ENV=$ENV python src/main.py
else
    python src/main.py
fi

# Deactivate virtual environment
deactivate
