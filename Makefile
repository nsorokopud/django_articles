COMPOSE = docker compose
SERVICE = web-app
SETTINGS = config.settings.production
PYTHON = python manage.py

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Available production commands:"
	@echo "  make prod-check-deploy"
	@echo "  make prod-wait-db"
	@echo "  make prod-migrate"
	@echo "  make prod-collectstatic"
	@echo "  make prod-collect-fixture-media"
	@echo "  make prod-load-fixtures"
	@echo "  make prod-backfill-article-content-text"
	@echo "  make prod-reset-article-publish-sequence"
	@echo "  make prod-createsuperuser"
	@echo "  make prod-container-shell"

.PHONY: prod-check-deploy prod-wait-db prod-migrate prod-collectstatic prod-container-shell
.PHONY: prod-load-fixtures prod-collect-fixture-media prod-backfill-article-content-text
.PHONY: prod-reset-article-publish-sequence prod-createsuperuser

prod-check-deploy:
	$(COMPOSE) run --rm --no-deps --entrypoint "" $(SERVICE) \
	$(PYTHON) check --deploy --settings=$(SETTINGS)

prod-wait-db:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) wait_for_db --settings=$(SETTINGS)

prod-migrate:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) migrate --settings=$(SETTINGS) --noinput

prod-collectstatic:
	$(COMPOSE) run --rm --no-deps --user root --entrypoint "" $(SERVICE) \
	sh -c '\
		mkdir -p /app/staticfiles && \
		chown -R articles_user:articles_user /app/staticfiles && \
		gosu articles_user $(PYTHON) collectstatic --settings=$(SETTINGS) --noinput \
	'

prod-collect-fixture-media:
	$(COMPOSE) run --rm --user root --entrypoint "" $(SERVICE) \
	sh -c '\
		mkdir -p /app/media && \
		chown -R articles_user:articles_user /app/media && \
		gosu articles_user $(PYTHON) collect_fixture_media --settings=$(SETTINGS) --noinput \
	'

prod-load-fixtures:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) loaddata fixtures/initial_data.json --settings=$(SETTINGS)

prod-backfill-article-content-text:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) backfill_article_content_text --settings=$(SETTINGS)

prod-reset-article-publish-sequence:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) reset_article_publish_sequence --settings=$(SETTINGS)

prod-createsuperuser:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	$(PYTHON) createsuperuser --settings=$(SETTINGS) --noinput

prod-container-shell:
	$(COMPOSE) run --rm --entrypoint "" $(SERVICE) \
	sh

-include Makefile.local
