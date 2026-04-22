.PHONY: update-tables seed-tables ci fix

SLUG ?=
ENV ?=

COMPOSE_FILES = -f docker-compose.yml $(if $(filter prod,$(ENV)),-f docker-compose.prod.yml --env-file .env.prod,)

update-tables:
	docker compose $(COMPOSE_FILES) exec api python scripts/update_tables.py $(if $(SLUG),--slug $(SLUG),)
	docker compose $(COMPOSE_FILES) exec api python scripts/seed_tables.py $(if $(SLUG),--slug $(SLUG),)

seed-tables:
	docker compose $(COMPOSE_FILES) exec api python scripts/seed_tables.py

ci:
	@echo "=== API: ruff ==="
	cd api && conda run -n ojik_bms ruff check app/ --select E,F,W,I,N,UP --ignore E501
	@echo "=== Client: ruff ==="
	cd client && conda run -n ojik_bms ruff check ojikbms_client/ --select E,F,W,I,N,UP --ignore E501
	@echo "=== Web: eslint ==="
	cd web && npm run lint --silent
	@echo "=== Web: tsc ==="
	cd web && npm run type-check --silent
	@echo "=== API: pytest ==="
	cd api && conda run -n ojik_bms sh -c 'python3 -m pytest tests/ -v --tb=short; code=$$?; [ $$code -eq 0 ] || [ $$code -eq 5 ]'
	@echo "=== Client: pytest ==="
	cd client && conda run -n ojik_bms python3 -m pytest tests/ -v --tb=short
	@echo "All checks passed."

fix:
	@echo "=== API: ruff fix ==="
	cd api && conda run -n ojik_bms ruff check app/ --select E,F,W,I,N,UP --ignore E501 --fix
	@echo "=== Client: ruff fix ==="
	cd client && conda run -n ojik_bms ruff check ojikbms_client/ --select E,F,W,I,N,UP --ignore E501 --fix
	@echo "Fix complete."
