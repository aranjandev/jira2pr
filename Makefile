.PHONY: help install init check run resume status list test

PYTHON ?= python3
ENGINE := $(CURDIR)/engine
CLI := PYTHONPATH=$(ENGINE)/compiler:$(ENGINE) $(PYTHON) $(ENGINE)/jira2pr/cli.py
TARGET_DIR ?= .
BACKEND ?= aider

help: ## Show available make targets
	@awk 'BEGIN {FS = ":.*## "; print "Usage: make <target>\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install jira2pr from this checkout with uv
	uv tool install --editable ./engine

init: ## Generate a platform-specific agent setup (PLATFORM=copilot|aider)
	$(CLI) init --platform "$(PLATFORM)" --target-dir "$(TARGET_DIR)"

check: ## Check whether generated output is up to date (PLATFORM=copilot|aider)
	$(CLI) check --platform "$(PLATFORM)" --target-dir "$(TARGET_DIR)"

run: ## Start a workflow (WORKFLOW=feature TICKET=PROJ-123)
	$(CLI) run "$(WORKFLOW)" "$(TICKET)" --backend "$(BACKEND)" --target-dir "$(TARGET_DIR)"

resume: ## Resume a workflow (TICKET=PROJ-123)
	$(CLI) resume "$(TICKET)" --backend "$(BACKEND)" --target-dir "$(TARGET_DIR)"

status: ## Show workflow status (TICKET=PROJ-123)
	$(CLI) status "$(TICKET)" --target-dir "$(TARGET_DIR)"

list: ## List known workflows
	$(CLI) list --target-dir "$(TARGET_DIR)"

test: ## Run the full unit test suite
	cd $(ENGINE) && $(PYTHON) -m pytest tests/ -q