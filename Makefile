.PHONY: update-tables seed-tables ci fix

SLUG ?=
URL ?=
ENV ?=
DEFAULT_ONLY ?=
ARGS ?=

COMPOSE_FILES = -f docker-compose.yml $(if $(filter prod,$(ENV)),-f docker-compose.prod.yml --env-file .env.prod,)
UPDATE_TABLE_ARGS = $(if $(SLUG),--slug $(SLUG),) $(if $(URL),--url $(URL),) $(if $(DEFAULT_ONLY),--default-only,) $(ARGS)
SEED_TABLE_ARGS = $(if $(SLUG),--slug $(SLUG),) $(if $(DEFAULT_ONLY),--default-only,) $(ARGS)

update-tables:
	docker compose $(COMPOSE_FILES) exec api python scripts/update_tables.py $(UPDATE_TABLE_ARGS)

seed-tables:
	docker compose $(COMPOSE_FILES) exec api python scripts/seed_tables.py $(SEED_TABLE_ARGS)

ci:
	@echo "=== API: ruff ==="
	cd api && conda run -n ojik_bms ruff check app/ --select E,F,W,I,N,UP --ignore E501
	@echo "=== Client: eslint ==="
	cd client && npm run lint --silent
	@echo "=== Client: tsc/vite ==="
	cd client && npm run build --silent
	@echo "=== Web: eslint ==="
	cd web && npm run lint --silent
	@echo "=== Web: tsc ==="
	cd web && npm run type-check --silent
	@echo "=== API: pytest ==="
	cd api && conda run -n ojik_bms sh -c 'python3 -m pytest tests/ -v --tb=short; code=$$?; [ $$code -eq 0 ] || [ $$code -eq 5 ]'
	@echo "=== Client: cargo test ==="
	cd client/src-tauri && cargo test
	@echo "All checks passed."

fix:
	@echo "=== API: ruff fix ==="
	cd api && conda run -n ojik_bms ruff check app/ --select E,F,W,I,N,UP --ignore E501 --fix
	@echo "=== Client: eslint fix ==="
	cd client && npm run lint --silent -- --fix
	@echo "Fix complete."
