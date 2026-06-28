#!/bin/bash

set -e

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p \
        /app/logs \
        /app/media \
        /app/staticfiles \
        /app/celerybeat

    chown articles_user:articles_user \
        /app/logs \
        /app/media \
        /app/staticfiles \
        /app/celerybeat

    exec gosu articles_user "$0" "$@"
fi

python manage.py wait_for_db

exec "$@"
