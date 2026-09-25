.PHONY: up down logs test api-test web-build
up:
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
api-test:
	cd apps/api && python -m pytest
web-build:
	cd apps/web && npm install && npm run build
test: api-test web-build
