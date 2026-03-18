.PHONY: update-tables ci fix

SLUG ?=

update-tables:
	docker compose exec api python scripts/update_tables.py $(if $(SLUG),--slug $(SLUG),)

fix:
	@echo "=== API: ruff fix ==="
	cd api && ruff check app/ --select E,F,W,I,N,UP --ignore E501 --fix
	@echo "=== Client: ruff fix ==="
	cd client && ruff check ojikbms_client/ --select E,F,W,I,N,UP --ignore E501 --fix
	@echo "Fix complete."

ci:
	@echo "=== API: ruff ==="
	cd api && ruff check app/ --select E,F,W,I,N,UP --ignore E501
	@echo "=== Client: ruff ==="
	cd client && ruff check ojikbms_client/ --select E,F,W,I,N,UP --ignore E501
	@echo "=== Web: eslint ==="
	cd web && npm run lint --silent
	@echo "=== Web: tsc ==="
	cd web && npm run type-check --silent
	@echo "=== API: pytest ==="
	cd api && conda run -n ojik_bms pytest tests/ -v --tb=short; \
	code=$$?; [ $$code -eq 0 ] || [ $$code -eq 5 ] || exit $$code
	@echo "=== Client: pytest ==="
	cd client && conda run -n ojik_bms pytest tests/ -v --tb=short
	@echo "All checks passed."