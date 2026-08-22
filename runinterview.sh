#!/bin/bash

PORT=12700
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/venv/bin/activate"

echo "Checking for existing processes on port $PORT..."

PID=$(lsof -ti:$PORT)

if [ -n "$PID" ]; then
    echo "Killing existing process(es) on port $PORT: $PID"
    kill -9 $PID
    sleep 1
fi

echo "Running migrations..."
source "$PROJECT_DIR/venv/bin/activate" && python manage.py migrate --noinput

echo "Starting Django server on port $PORT..."
source "$PROJECT_DIR/venv/bin/activate" && python manage.py runserver 0.0.0.0:$PORT