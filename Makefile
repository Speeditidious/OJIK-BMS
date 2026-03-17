.PHONY: update-tables

SLUG ?=

update-tables:
	docker compose exec api python scripts/update_tables.py $(if $(SLUG),--slug $(SLUG),)
