# RepoPilot AI Makefile

.PHONY: setup install dev test clean frontend backend all

# Default target
all: setup

# Initial setup
setup:
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  Windows: .\\venv\\Scripts\\activate"
	@echo "  Unix: source venv/bin/activate"
	@echo "Then run: make install"

# Install dependencies
install:
	pip install -r backend/requirements.txt

# Run backend dev server
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Run frontend dev server
frontend:
	cd frontend && npm run dev

# Run both (requires two terminals)
dev:
	@echo "Run in separate terminals:"
	@echo "  Terminal 1: make backend"
	@echo "  Terminal 2: make frontend"

# Run tests
test:
	cd backend && pytest -v

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Health check
health:
	curl -s http://localhost:8000/health | python -m json.tool
