#!/bin/bash

./manage.py wait_for_db
./manage.py migrate --noinput
./manage.py collect_fixture_media --noinput;
./manage.py loaddata fixtures/initial_data.json
./manage.py createsuperuser --noinput
./manage.py collectstatic --noinput

if [ "$SCHEME" == "http" ]; then
    ./manage.py runserver 0.0.0.0:8000  # Local development only!
elif [ "$SCHEME" == "https" ]; then
    daphne -b 0.0.0.0 -p 8000  config.asgi:application
else
    echo "Error! Invalid SCHEME value: '$SCHEME'" >&2
fi

exec "$@"
