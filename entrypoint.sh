#!/bin/bash
set -e

echo "Running Atenea internal migrations..."
python manage.py migrate

echo "Starting Gunicorn server..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
