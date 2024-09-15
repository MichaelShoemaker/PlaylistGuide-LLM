# Makefile for Docker Compose

# Variables
DOCKER_COMPOSE = docker compose

# Start all services
up:
	$(DOCKER_COMPOSE) up -d

# Stop all services
down:
	$(DOCKER_COMPOSE) down

# Restart all services
restart:
	$(DOCKER_COMPOSE) down && $(DOCKER_COMPOSE) up -d

# Rebuild and restart all services
rebuild:
	$(DOCKER_COMPOSE) down && $(DOCKER_COMPOSE) build --no-cache && $(DOCKER_COMPOSE) up -d

# Start a specific service (example: make start-streamlit_app)
start-%:
	$(DOCKER_COMPOSE) up -d $*

# Stop a specific service (example: make stop-streamlit_app)
stop-%:
	$(DOCKER_COMPOSE) stop $*

# Restart a specific service (example: make restart-streamlit_app)
restart-%:
	$(DOCKER_COMPOSE) stop $* && $(DOCKER_COMPOSE) up -d $*

# Rebuild and restart a specific service (example: make rebuild-streamlit_app)
rebuild-%:
	$(DOCKER_COMPOSE) stop $* && $(DOCKER_COMPOSE) build --no-cache $* && $(DOCKER_COMPOSE) up -d $*

# Logs for a specific service (example: make logs-streamlit_app)
logs-%:
	$(DOCKER_COMPOSE) logs -f $*

# View logs for all services
logs:
	$(DOCKER_COMPOSE) logs -f

# Check the status of all services
ps:
	$(DOCKER_COMPOSE) ps

# Clean up (remove volumes and network)
clean:
	$(DOCKER_COMPOSE) down -v --remove-orphans

# Health check for Elasticsearch
check-elasticsearch:
	curl -f http://localhost:9200 || (echo "Elasticsearch is down" && exit 1)

# Health check for PostgreSQL
check-postgres:
	PGPASSWORD=$(POSTGRES_PASSWORD) psql -h localhost -U $(POSTGRES_USER) -d $(POSTGRES_DB) -c '\l' || (echo "PostgreSQL is down" && exit 1)
