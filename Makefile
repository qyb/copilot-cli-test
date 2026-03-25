.PHONY: help install test test-fast test-verbose test-coverage \
        run-test-server test-integration lint clean docs

help:
	@echo "NAT Router Test Suite - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install           Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all unit tests"
	@echo "  make test-fast         Run fast unit tests (structure only)"
	@echo "  make test-verbose      Run tests with verbose output"
	@echo "  make test-coverage     Run tests with coverage report"
	@echo ""
	@echo "Running:"
	@echo "  make run-test-server   Start test.py HTTP server"
	@echo "  make test-integration  Run integration tests (requires server running)"
	@echo ""
	@echo "Development:"
	@echo "  make clean             Clean temporary files and cache"
	@echo "  make docs              Show documentation"

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

test-fast:
	.venv/bin/pytest tests/ -v --tb=short -k "not run"

test-verbose:
	.venv/bin/pytest tests/ -vv --tb=long

test-coverage:
	.venv/bin/pytest tests/ --cov=test --cov-report=html --cov-report=term
	@echo ""
	@echo "Coverage report generated: htmlcov/index.html"

run-test-server:
	@echo "Starting test.py HTTP server..."
	.venv/bin/python test.py

run-test-server-debug:
	@echo "Starting test.py HTTP server (debug mode)..."
	.venv/bin/python test.py --debug

test-integration:
	@echo "Running integration tests..."
	@echo "Make sure test.py is running on http://10.0.0.20:8888"
	.venv/bin/python integration_test.py http://10.0.0.20:8888

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name ".venv" -prune -o -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

docs:
	@echo ""
	@echo "=== Main Documentation ==="
	@echo "  README.md            - Project overview"
	@echo "  AGENTS.md            - VPS deployment topology"
	@echo ""
	@echo "=== Detailed Guides ==="
	@echo "  docs/test.md         - test.py HTTP API usage"
	@echo "  docs/verify.md       - Verification scenarios and troubleshooting"
	@echo "  docs/env.md          - sudo NOPASSWD configuration"
	@echo ""
	@echo "View with: cat <filename> or less <filename>"
	@echo ""

.PHONY: quick-start quick-test

quick-start:
	@echo "Quick Start - One-liner setup:"
	@echo ""
	@echo "  1. Install: make install"
	@echo "  2. In terminal 1: make run-test-server"
	@echo "  3. In terminal 2: make test-integration"
	@echo ""

quick-test:
	@echo "Running quick test..."
	@.venv/bin/pytest tests/ -v --tb=line -q 2>&1 | tail -20
