#!/bin/bash

# PromptRCA Docker Hub Push Script
# This script builds and pushes both Lambda and Server images to Docker Hub
# Uses Docker BuildKit for multi-platform builds (x86_64 and arm64)

set -e  # Exit on any error

# Configuration
DOCKERHUB_USERNAME="promptrca"
SERVER_IMAGE="server"
LAMBDA_IMAGE="lambda"
VERSION=${VERSION:-"latest"}
PLATFORMS="linux/amd64,linux/arm64"

# Enable Docker BuildKit
export DOCKER_BUILDKIT=1
export DOCKER_CLI_EXPERIMENTAL=enabled

echo "🚀 PromptRCA Docker Hub Push Script (Multi-Platform)"
echo "=================================================="
echo "Docker Hub Username: $DOCKERHUB_USERNAME"
echo "Version: $VERSION"
echo "Server Image: $DOCKERHUB_USERNAME/$SERVER_IMAGE:$VERSION"
echo "Lambda Image: $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:$VERSION"
echo "Platforms: $PLATFORMS"
echo ""

# Note: Make sure you're logged in to Docker Hub and AWS ECR
echo "ℹ️  Make sure you're logged in to:"
echo "   - Docker Hub (run 'docker login')"
echo "   - AWS ECR (run 'aws-vault exec personal --no-session -- aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws')"
echo ""

# Build and push Server image (multi-platform)
echo "🔨 Building Server image for multiple platforms..."
docker buildx build \
  --platform $PLATFORMS \
  --file Dockerfile.server \
  --tag $DOCKERHUB_USERNAME/$SERVER_IMAGE:$VERSION \
  --tag $DOCKERHUB_USERNAME/$SERVER_IMAGE:latest \
  --push \
  .
echo "✅ Server image built and pushed for all platforms"

# Build and push Lambda image (multi-platform)
echo "🔨 Building Lambda image for multiple platforms..."
docker buildx build \
  --platform $PLATFORMS \
  --file Dockerfile.lambda \
  --tag $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:$VERSION \
  --tag $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:latest \
  --push \
  .
echo "✅ Lambda image built and pushed for all platforms"

echo ""
echo "🎉 All images pushed successfully!"
echo ""
echo "Your images are now available at:"
echo "  - $DOCKERHUB_USERNAME/$SERVER_IMAGE:$VERSION"
echo "  - $DOCKERHUB_USERNAME/$SERVER_IMAGE:latest"
echo "  - $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:$VERSION"
echo "  - $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:latest"
echo ""
echo "To pull and run:"
echo "  docker pull $DOCKERHUB_USERNAME/$SERVER_IMAGE:$VERSION  # Server version"
echo "  docker pull $DOCKERHUB_USERNAME/$SERVER_IMAGE:latest    # Latest server"
echo "  docker pull $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:$VERSION  # Lambda version"
echo "  docker pull $DOCKERHUB_USERNAME/$LAMBDA_IMAGE:latest    # Latest lambda"
