build:
	docker compose -p bamboo -f local.yml up --build -d --remove-orphans


up:
	docker compose -p bamboo -f local.yml up -d

down-v:
	docker compose -f local.yml down -v

down:
	docker compose -p bamboo -f local.yml down

bamboo-config:
	docker compose -f local.yml config

makemigrations:
	docker compose -f local.yml exec -it api alembic revision --autogenerate -m "$(name)"

migrate:
	docker compose -p bamboo -f local.yml exec -it api alembic upgrade head

history:
	docker compose -f local.yml exec -it api alembic history

current-migration:
	docker compose -f local.yml exec -it api alembic current

downgrade:
	docker compose -f local.yml exec -it api alembic downgrade $(version)

inspect-network:
	docker network inspect bamboo_local_nw

psql:
	docker compose -p bamboo -f local.yml exec -it postgres psql -U postgres -d bamboo_fastapi_bank


