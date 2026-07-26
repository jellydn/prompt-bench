default: dev

dev:
	docker compose up --build

backend-dev:
	cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm install && npm run dev

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check .

lint-frontend:
	cd frontend && npx eslint .

format: format-backend format-frontend

format-backend:
	cd backend && uv run ruff format .

format-frontend:
	cd frontend && npx prettier --write .

format-check: format-check-backend format-check-frontend

format-check-backend:
	cd backend && uv run ruff format --check .

format-check-frontend:
	cd frontend && npx prettier --check .

clean:
	rm -rf backend/.venv backend/promptbench.db frontend/node_modules frontend/dist frontend/tsconfig.tsbuildinfo frontend/tsconfig.node.tsbuildinfo

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
