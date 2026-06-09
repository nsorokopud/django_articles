#!/bin/bash

set -e

mkdir -p /app/logs
chown -R articles_user:articles_user /app/logs

# Re-exec this script as articles_user
if [ "$(whoami)" != "articles_user" ]; then
    exec gosu articles_user "$0" "$@"
fi

./manage.py wait_for_db

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
