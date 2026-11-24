.PHONY: help up down logs build test clean

help:
	@echo "Lyftr AI Chatbot Commands:"
	@echo "  make up      - Build and start all services via Docker Compose"
	@echo "  make down    - Stop and remove all Docker Compose containers"
	@echo "  make build   - Rebuild Docker images without cache"
	@echo "  make logs    - Stream container logs in real time"
	@echo "  make test    - Run backend Pytest suite locally"
	@echo "  make clean   - Remove build artifacts and temporary files"

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest tests -v

clean:
	rm -rf backend/.pytest_cache frontend/dist

