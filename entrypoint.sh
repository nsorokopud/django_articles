#!/bin/sh

echo "Waiting for DB..."

while ! nc -z db 5432; do
    sleep 0.1
done

echo "DB started"

if [ ! -d /app/staticfiles/css ]; then
    python manage.py flush --no-input
    python manage.py migrate
    python manage.py collectfixturemedia --noinput;
    python manage.py loaddata fixtures/initial_data.json
    python manage.py createsuperuser --no-input
    python manage.py collectstatic --noinput
else
    echo "Container is getting restarted. Skipping initialization."
fi

daphne -b 0.0.0.0 -p 8000  config.asgi:application

exec "$@"
