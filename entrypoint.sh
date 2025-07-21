#!/bin/bash

set -e

mkdir -p /app/logs /app/staticfiles
chown -R articles_user:articles_user /app/logs /app/staticfiles

# Re-exec this script as articles_user
if [ "$(whoami)" != "articles_user" ]; then
    exec gosu articles_user "$0" "$@"
fi

./manage.py wait_for_db
./manage.py migrate --noinput
./manage.py collect_fixture_media --noinput
./manage.py loaddata fixtures/initial_data.json
./manage.py createsuperuser --noinput || true
./manage.py collectstatic --noinput

if [ $# -eq 0 ]; then
    if [ "$SCHEME" == "http" ]; then
        exec ./manage.py runserver 0.0.0.0:8000
    elif [ "$SCHEME" == "https" ]; then
        exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
    else
        echo "Error! Invalid SCHEME value: '$SCHEME'" >&2
        exit 1
    fi
else
    exec "$@"
fi
