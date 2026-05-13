.PHONY: help install dev up down migrate revision seed seed-demo seed-ready seed-conflict seed-checked-in seed-history reset-run test lint fmt clean

help:
	@echo "make install        - create venv and install deps"
	@echo "make up             - start postgres + mosquitto via docker-compose"
	@echo "make down           - stop docker-compose services"
	@echo "make migrate        - apply latest alembic migrations"
	@echo "make revision m='msg' - create a new alembic migration"
	@echo "make seed           - reset app tables and load demo seed data"
	@echo "make seed-demo      - same as make seed"
	@echo "make seed-ready     - load demo + ready-to-arrive reservation scenario"
	@echo "make seed-conflict  - load demo + strong-conflict demo scenario"
	@echo "make seed-checked-in - load demo + checked-in reservation scenario"
	@echo "make seed-history   - load demo + payment-history scenario"
	@echo "make reset-run      - down + up + migrate + seed + dev"
	@echo "make dev            - run the backend process (HTTP + Socket.IO + MQTT + jobs)"
	@echo "make test           - run pytest against a real postgres cluster"
	@echo "make lint           - ruff + mypy"
	@echo "make fmt            - ruff format"

install:
	python3.11 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e '.[dev]'

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

migrate:
	.venv/bin/alembic upgrade head

revision:
	.venv/bin/alembic revision --autogenerate -m "$(m)"

seed:
	.venv/bin/python scripts/seed.py

seed-demo:
	.venv/bin/python scripts/seed.py

seed-ready:
	.venv/bin/python scripts/seed.py --dataset integration_ready

seed-conflict:
	.venv/bin/python scripts/seed.py --dataset integration_conflict

seed-checked-in:
	.venv/bin/python scripts/seed.py --dataset integration_checked_in

seed-history:
	.venv/bin/python scripts/seed.py --dataset payments_history

reset-run:
	$(MAKE) down
	$(MAKE) up
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) dev

dev:
	.venv/bin/python -m app.web

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check app tests
	.venv/bin/mypy app

fmt:
	.venv/bin/ruff format app tests

clean:
	rm -rf .venv .pytest_cache .coverage htmlcov dist build *.egg-info
