PYTHON ?= python

.PHONY: install lint typecheck test test-browser test-qdrant test-models test-container eval card card-check verify verify-browser verify-qdrant verify-openai verify-models verify-container verify-full-local run seed-fixture qdrant-up qdrant-down graph

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check app tests

typecheck:
	$(PYTHON) -m mypy app

test:
	$(PYTHON) -m pytest -m "not live_openai and not requires_browser and not requires_qdrant and not requires_model_download"

test-browser:
	$(PYTHON) -m pytest -m requires_browser

test-qdrant:
	$(PYTHON) -m pytest -m requires_qdrant

test-models:
	$(PYTHON) -m pytest -m requires_model_download

test-container:
	$(PYTHON) -m pytest tests/unit/test_container_config.py

eval:
	$(PYTHON) -m scripts.run_evals --headline metrics/headline.json

# Render docs/assets/metrics.svg and the README results block from metrics/headline.json.
card: eval
	$(PYTHON) metrics/render.py

card-check:
	$(PYTHON) metrics/render.py --check

verify:
	$(PYTHON) -m scripts.verify default

verify-browser:
	$(PYTHON) -m scripts.verify browser

verify-qdrant:
	$(PYTHON) -m scripts.verify qdrant

verify-openai:
	$(PYTHON) -m scripts.verify openai

verify-models:
	$(PYTHON) -m scripts.verify models

verify-container:
	$(PYTHON) -m scripts.verify container

verify-full-local:
	$(PYTHON) -m scripts.verify full-local

run:
	$(PYTHON) -m uvicorn app.main:app --reload

seed-fixture:
	$(PYTHON) -m app.ingestion.loaders app/evals/fixtures/synthetic_rulebook.md

qdrant-up:
	docker compose up -d qdrant

qdrant-down:
	docker compose down

graph:
	graphify update . && graphify cluster-only . --no-viz --no-label
