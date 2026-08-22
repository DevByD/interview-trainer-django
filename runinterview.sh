#!/bin/bash

PORT=12700

echo "Checking for existing processes on port $PORT..."

PID=$(lsof -ti:$PORT)

if [ -n "$PID" ]; then
    echo "Killing existing process(es) on port $PORT: $PID"
    kill -9 $PID
    sleep 1
fi

echo "Running migrations..."
/Users/amolc/2026/interview-trainer-django/venv/bin/python manage.py migrate --noinput

echo "Starting Django server on port $PORT..."
/Users/amolc/2026/interview-trainer-django/venv/bin/python manage.py runserver 0.0.0.0:$PORT