.PHONY: help install test lint

PYTHON := uv run python3
ENGINE := $(CURDIR)/engine

help: ## Show available make targets
	@awk 'BEGIN {FS = ":.*## "; print "Usage: make <target>\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install jira2pr from this checkout
	uv tool install --reinstall --editable ./engine

test: ## Run the full unit test suite
	cd $(ENGINE) && $(PYTHON) -m pytest tests/ -q

lint: ## Lint the code using ruff
	$(PYTHON) -m ruff check $(if $(FIX),--fix,) $(ENGINE)
