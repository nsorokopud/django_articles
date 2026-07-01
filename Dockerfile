# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

ARG REQUIREMENTS_FILE=requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Always needed because requirements-dev.txt imports it
COPY requirements.txt /build/requirements.txt

# Production: requirements.txt
# Development: requirements-dev.txt
COPY ${REQUIREMENTS_FILE} /build/selected-requirements.txt

RUN python -m pip wheel \
        --no-cache-dir \
        --wheel-dir /wheels \
        -r /build/selected-requirements.txt


FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gosu \
        libmagic1 \
        libpq5 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos "" articles_user

RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    --mount=type=bind,from=builder,source=/build,target=/requirements \
    python -m pip install \
        --no-cache-dir \
        --no-index \
        --find-links=/wheels \
        -r /requirements/selected-requirements.txt

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN sed -i 's/\r$//g' /usr/local/bin/entrypoint.sh && \
    chmod 755 /usr/local/bin/entrypoint.sh

COPY --exclude=requirements-dev.txt . .

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
