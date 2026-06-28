COMPOSE := docker compose -f docker-compose.yaml
SERVICE := web-app
SETTINGS := config.settings.production
PYTHON := python manage.py

RUN_APP := $(COMPOSE) run --rm --user articles_user --entrypoint "" $(SERVICE)

RUN_APP_NO_DEPS := $(COMPOSE) run --rm \
	--no-deps \
	--user articles_user \
	--entrypoint "" \
	$(SERVICE)

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

.PHONY: prod-check-deploy
.PHONY: prod-wait-db
.PHONY: prod-migrate
.PHONY: prod-collectstatic
.PHONY: prod-collect-fixture-media
.PHONY: prod-load-fixtures
.PHONY: prod-backfill-article-content-text
.PHONY: prod-reset-article-publish-sequence
.PHONY: prod-createsuperuser
.PHONY: prod-container-shell

prod-check-deploy:
	$(RUN_APP_NO_DEPS) $(PYTHON) check --deploy --settings=$(SETTINGS)

prod-wait-db:
	$(RUN_APP) $(PYTHON) wait_for_db --settings=$(SETTINGS)

prod-migrate:
	$(RUN_APP) $(PYTHON) migrate --settings=$(SETTINGS) --noinput

prod-collectstatic:
	$(COMPOSE) run --rm \
	--no-deps \
	--user root \
	--entrypoint "" \
	$(SERVICE) \
	sh -c '\
		mkdir -p /app/staticfiles && \
		chown -R articles_user:articles_user /app/staticfiles && \
		exec gosu articles_user $(PYTHON) collectstatic \
			--settings=$(SETTINGS) \
			--noinput \
	'

prod-collect-fixture-media:
	$(COMPOSE) run --rm \
	--user root \
	--entrypoint "" \
	$(SERVICE) \
	sh -c '\
		mkdir -p /app/media && \
		chown -R articles_user:articles_user /app/media && \
		exec gosu articles_user $(PYTHON) collect_fixture_media \
			--settings=$(SETTINGS) \
			--noinput \
	'

prod-load-fixtures:
	$(RUN_APP) $(PYTHON) loaddata fixtures/initial_data.json --settings=$(SETTINGS)

prod-backfill-article-content-text:
	$(RUN_APP) $(PYTHON) backfill_article_content_text --settings=$(SETTINGS)

prod-reset-article-publish-sequence:
	$(RUN_APP) $(PYTHON) reset_article_publish_sequence --settings=$(SETTINGS)

prod-createsuperuser:
	$(RUN_APP) $(PYTHON) createsuperuser --settings=$(SETTINGS) --noinput

prod-container-shell:
	$(RUN_APP) sh

-include Makefile.local
