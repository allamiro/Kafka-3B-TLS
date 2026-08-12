# =============================================================================
# Kafka 3.9.2 + ZooKeeper 3.9.5 Docker Compose Lab — Makefile
# =============================================================================
SHELL := /bin/bash

COMPOSE_FILE ?= docker-compose.generated.yml
DC           := docker compose -f $(COMPOSE_FILE)

# Sizing/mode (override on the command line: make render BROKERS=5 ZOOKEEPERS=3)
BROKERS      ?= $(shell grep -E '^BROKER_COUNT=' .env 2>/dev/null | cut -d= -f2 || echo 3)
ZOOKEEPERS   ?= $(shell grep -E '^ZOOKEEPER_COUNT=' .env 2>/dev/null | cut -d= -f2 || echo 3)
SECURITY     ?= $(shell grep -E '^KAFKA_SECURITY_MODE=' .env 2>/dev/null | cut -d= -f2 || echo dual)

# Topic helpers
TOPIC               ?= test-events
PARTITIONS          ?= 6
REPLICATION_FACTOR  ?= 3

.DEFAULT_GOAL := help

.PHONY: help env certs render build up up-plaintext up-ssl down clean ps logs \
        validate vendor-sync create-topic list-topics describe \
        produce-plaintext consume-plaintext produce-ssl consume-ssl \
        test-deps test test-fast test-integration test-all lint

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@[ -f .env ] || { cp .env.example .env && echo "Created .env from .env.example"; }

validate: ## Validate .env sizing and security mode
	@bash scripts/validate-env.sh

certs: env ## Generate or import SSL material (per KAFKA_CERT_MODE / KAFKA_SECURITY_MODE)
	@bash scripts/prepare-certs.sh

render: env ## Render docker-compose.generated.yml (BROKERS=, ZOOKEEPERS=, SECURITY=)
	@python3 scripts/render-compose.py --brokers $(BROKERS) --zookeepers $(ZOOKEEPERS) \
	    --security-mode $(SECURITY) -o $(COMPOSE_FILE)

vendor-sync: ## Copy provided packages/ tarballs into vendor/ for air-gapped builds
	@cp -f packages/kafka_2.13-3.9.2.tgz vendor/ 2>/dev/null && echo "kafka tgz -> vendor/" || echo "kafka tgz not found in packages/"
	@if [ -f packages/apache-zookeeper-3.9.5-bin.tar.gz ]; then \
	    cp -f packages/apache-zookeeper-3.9.5-bin.tar.gz vendor/ && echo "zookeeper -bin -> vendor/"; \
	  else echo "WARNING: packages/apache-zookeeper-3.9.5-bin.tar.gz not found (the bundled ZK is a SOURCE dist; fetch the -bin tarball)"; fi

build: ## Build images (uses vendor/ tarballs if present, else downloads)
	@test -f $(COMPOSE_FILE) || $(MAKE) render
	@$(DC) build

up: ## Render (if needed), check certs, then start the full cluster
	@test -f $(COMPOSE_FILE) || $(MAKE) render
	@if grep -qE '^KAFKA_SECURITY_MODE=(ssl|dual)' .env 2>/dev/null && \
	    [ ! -f certs/generated/kafka1/kafka.server.keystore.p12 ]; then \
	      echo "SSL material is missing. Run: make certs"; exit 1; fi
	@$(DC) up -d --build
	@echo "Cluster starting. Track readiness with: make ps  /  ./scripts/wait-for-kafka.sh"

up-plaintext: ## Start a PLAINTEXT-only cluster
	@$(MAKE) render SECURITY=plaintext
	@$(DC) up -d --build

up-ssl: ## Start an SSL-only cluster (requires certs)
	@$(MAKE) certs
	@$(MAKE) render SECURITY=ssl
	@$(DC) up -d --build

down: ## Stop the cluster (keep volumes)
	@$(DC) down --remove-orphans

clean: ## Stop and remove containers, networks, and volumes
	@bash scripts/clean.sh

ps: ## Show cluster status
	@$(DC) ps

logs: ## Tail logs (use SVC=kafka1 to scope)
	@$(DC) logs -f $(SVC)

create-topic: ## Create a topic (TOPIC=, PARTITIONS=, REPLICATION_FACTOR=, SECURITY=)
	@TOPIC=$(TOPIC) PARTITIONS=$(PARTITIONS) REPLICATION_FACTOR=$(REPLICATION_FACTOR) \
	  SECURITY=$(SECURITY) BOOTSTRAP_SERVER=$(BOOTSTRAP_SERVER) bash scripts/create-topic.sh

list-topics: ## List topics (SECURITY=plaintext|ssl)
	@SECURITY=$(SECURITY) bash scripts/list-topics.sh

describe: ## Describe brokers and topics (SECURITY=plaintext|ssl)
	@SECURITY=$(SECURITY) bash scripts/describe-cluster.sh

produce-plaintext: ## Interactive PLAINTEXT producer (TOPIC=)
	@TOPIC=$(TOPIC) bash scripts/produce-plaintext.sh

consume-plaintext: ## PLAINTEXT consumer from beginning (TOPIC=)
	@TOPIC=$(TOPIC) bash scripts/consume-plaintext.sh

produce-ssl: ## Interactive SSL producer (TOPIC=)
	@TOPIC=$(TOPIC) bash scripts/produce-ssl.sh

consume-ssl: ## SSL consumer from beginning (TOPIC=)
	@TOPIC=$(TOPIC) bash scripts/consume-ssl.sh

# ---------------------------------------------------------------------------
# Tests and linting  (see tests/README.md)
# ---------------------------------------------------------------------------

test-deps: ## Install the test dependencies (pytest, PyYAML)
	@python3 -m pip install --upgrade pip -r tests/requirements.txt

test: ## Run the unit tests (no Docker required)
	@python3 -m pytest

test-fast: ## Unit tests without the certificate suite
	@python3 -m pytest -m "not slow and not integration"

test-integration: ## End-to-end cluster tests (requires Docker; stop `make up` first)
	@python3 -m pytest -m integration

test-all: ## Every test, unit and end-to-end
	@python3 -m pytest -m ""

lint: ## Lint shell, YAML and Dockerfiles (skips tools that are not installed)
	@command -v shellcheck >/dev/null && shellcheck --severity=warning scripts/*.sh images/*/entrypoint.sh \
	  || echo "shellcheck not installed - skipped"
	@for f in $$(git ls-files '*.sh'); do bash -n "$$f" || exit 1; done; echo "bash -n: all scripts parse"
	@command -v yamllint >/dev/null && yamllint -c .yamllint.yml . \
	  || echo "yamllint not installed - skipped"
