# Sherlock Core - Docker Build and Run Makefile

# Variables
IMAGE_NAME = sherlock-core
TAG = latest
FULL_IMAGE = $(IMAGE_NAME):$(TAG)
CONTAINER_NAME = sherlock-test
PORT = 9000

# Default target
.PHONY: help
help: ## Show this help message
	@echo "Sherlock Core - Docker Operations"
	@echo "================================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## Build the Docker image
	@echo "🔨 Building Sherlock Core Docker image..."
	@echo "Image: $(FULL_IMAGE)"
	docker build -t $(FULL_IMAGE) .
	@echo "✅ Build completed successfully!"

.PHONY: run
run: ## Run the container locally (with port mapping)
	@echo "🚀 Starting Sherlock Core container..."
	@echo "Container: $(CONTAINER_NAME)"
	@echo "Port: http://localhost:$(PORT)"
	@echo ""
	@echo "To test the Lambda function:"
	@echo "curl -X POST \"http://localhost:$(PORT)/2015-03-31/functions/function/invocations\" \\"
	@echo "  -d '{\"free_text_input\": \"Test investigation\"}' \\"
	@echo "  -H \"Content-Type: application/json\""
	@echo ""
	@echo "Note: Without AWS credentials, the function will return an error."
	@echo "For local testing with AWS credentials, use: make run-with-aws"
	@echo ""
	docker run --rm -p $(PORT):8080 --name $(CONTAINER_NAME) $(FULL_IMAGE)

.PHONY: run-detached
run-detached: ## Run the container in background
	@echo "🚀 Starting Sherlock Core container in background..."
	docker run -d --rm -p $(PORT):8080 --name $(CONTAINER_NAME) $(FULL_IMAGE)

.PHONY: run-with-aws
run-with-aws: ## Run container with AWS credentials from environment
	@echo "🚀 Starting Sherlock Core container with AWS credentials..."
	@echo "Container: $(CONTAINER_NAME)"
	@echo "Port: http://localhost:$(PORT)"
	@echo ""
	@echo "Make sure you have AWS credentials configured:"
	@echo "  - AWS_ACCESS_KEY_ID"
	@echo "  - AWS_SECRET_ACCESS_KEY"
	@echo "  - AWS_DEFAULT_REGION (optional, defaults to us-east-1)"
	@echo ""
	@echo "To test the Lambda function:"
	@echo "curl -X POST \"http://localhost:$(PORT)/2015-03-31/functions/function/invocations\" \\"
	@echo "  -d '{\"free_text_input\": \"Test investigation\"}' \\"
	@echo "  -H \"Content-Type: application/json\""
	@echo ""
	docker run --rm -p $(PORT):8080 --name $(CONTAINER_NAME) \
		-e AWS_ACCESS_KEY_ID \
		-e AWS_SECRET_ACCESS_KEY \
		-e AWS_SESSION_TOKEN \
		-e AWS_DEFAULT_REGION \
		$(FULL_IMAGE)

.PHONY: run-with-aws-detached
run-with-aws-detached: ## Run container with AWS credentials in background
	@echo "🚀 Starting Sherlock Core container with AWS credentials in background..."
	@echo "Make sure you have AWS credentials configured in your environment"
	docker run -d --rm -p $(PORT):8080 --name $(CONTAINER_NAME) \
		-e AWS_ACCESS_KEY_ID \
		-e AWS_SECRET_ACCESS_KEY \
		-e AWS_SESSION_TOKEN \
		-e AWS_DEFAULT_REGION \
		$(FULL_IMAGE)
	@echo "✅ Container started. Access at http://localhost:$(PORT)"

.PHONY: stop
stop: ## Stop the running container
	@echo "🛑 Stopping Sherlock Core container..."
	-docker stop $(CONTAINER_NAME)
	@echo "✅ Container stopped"

.PHONY: test
test: ## Test the Lambda function with a sample event
	@echo "🧪 Testing Sherlock Core Lambda function..."
	@echo "Sending test event..."
	curl -X POST "http://localhost:$(PORT)/2015-03-31/functions/function/invocations" \
		-d '{"free_text_input": "Test Lambda function investigation"}' \
		-H "Content-Type: application/json"
	@echo ""
	@echo "✅ Test completed"

.PHONY: logs
logs: ## Show container logs
	@echo "📋 Showing container logs..."
	docker logs $(CONTAINER_NAME)

.PHONY: shell
shell: ## Open a shell in the running container
	@echo "🐚 Opening shell in container..."
	docker exec -it $(CONTAINER_NAME) /bin/bash

.PHONY: clean
clean: ## Clean up containers and images
	@echo "🧹 Cleaning up..."
	-docker stop $(CONTAINER_NAME) 2>/dev/null || true
	-docker rm $(CONTAINER_NAME) 2>/dev/null || true
	-docker rmi $(FULL_IMAGE) 2>/dev/null || true
	@echo "✅ Cleanup completed"

.PHONY: rebuild
rebuild: clean build ## Clean and rebuild the image

.PHONY: status
status: ## Show container status
	@echo "📊 Container Status:"
	@docker ps -a --filter name=$(CONTAINER_NAME) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

.PHONY: inspect
inspect: ## Inspect the Docker image
	@echo "🔍 Inspecting Docker image..."
	docker inspect $(FULL_IMAGE)

.PHONY: push
push: ## Push image to registry (requires registry configuration)
	@echo "📤 Pushing image to registry..."
	@echo "Note: Configure your registry before pushing"
	@echo "Example: docker tag $(FULL_IMAGE) your-registry/$(FULL_IMAGE)"
	@echo "        docker push your-registry/$(FULL_IMAGE)"

# Development targets
.PHONY: dev-run
dev-run: build run ## Build and run in one command

.PHONY: dev-test
dev-test: run-detached test stop ## Run container, test, and stop

.PHONY: dev-cycle
dev-cycle: clean build run ## Full development cycle: clean, build, run
