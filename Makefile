.PHONY: help build lint fmt clean uv ci ci-fmt

SCRIPT = scripts/build.py
STATUS = \033[1m\033[32m==>\033[0m

help: ## Show this help
	@printf "Usage: make [target]\n"
	@printf ""
	@printf "Available targets:\n"
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/: /' | sed 's/^/  /' | column -t -s:

uv: ## Initialize uv and install dependencies
	@printf "$(STATUS) Syncing dependencies\n"
	uv sync --all-extras

lint: ## Lint build.py with autofix
	@printf "$(STATUS) Linting\n"
	uv run ruff check $(SCRIPT) --fix
	uv run mypy $(SCRIPT)

fmt: ## Format repository
	@printf "$(STATUS) Formatting\n"
	uv run ruff format $(SCRIPT)
	taplo format --config '.taplo.toml'
	uv run mdformat .
	uv run yamlfix .

ci-fmt: ## Format repository (ignore .github)
	@printf "$(STATUS) Formatting (ignoring .github)\n"
	uv run ruff format $(SCRIPT)
	find . -name "*.toml" ! -path "./.github/*" -print -exec taplo format --config '.taplo.toml' {} +
	find . -name "*.md" ! -path "./.github/*" -print -exec uv run mdformat {} +
	uv run yamlfix . --exclude '.github'

build: ## Build catppuccin-kicad.zip
	@printf "$(STATUS) Building\n"
	uv run python $(SCRIPT)

all: ## Main target
	$(MAKE) uv
	$(MAKE) lint
	$(MAKE) fmt
	$(MAKE) build

ci: ## CI target
	$(MAKE) uv
	$(MAKE) lint
	$(MAKE) ci-fmt
	$(MAKE) build

clean: ## Remove build artifacts
	@printf "$(STATUS) Cleaning\n"
	rm -f "catppuccin-kicad-v*.zip"
	rm -rf '.venv/' '__pycache__' '.mypy_cache'
