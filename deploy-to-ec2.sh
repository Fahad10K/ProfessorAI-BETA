#!/bin/bash

# ProfessorAI - EC2 Deployment Script
# Usage: ./deploy-to-ec2.sh

set -e  # Exit on error

echo "🚀 Starting ProfessorAI Deployment..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file with your API keys"
    exit 1
fi

echo -e "${GREEN}✓ .env file found${NC}"

# Stop old containers
echo "📦 Stopping old containers..."
docker-compose -f docker-compose-production.yml down || true

# Clean up old images (optional - comment out to keep)
echo "🧹 Cleaning up old Docker images..."
docker system prune -f

# Build new image
echo "🔨 Building Docker image..."
docker-compose -f docker-compose-production.yml build

# Start services
echo "🚀 Starting services..."
docker-compose -f docker-compose-production.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

# Check status
echo "📊 Checking container status..."
docker-compose -f docker-compose-production.yml ps

# Test API
echo "🧪 Testing API health endpoint..."
if curl -f http://localhost:5001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is responding!${NC}"
else
    echo -e "${RED}✗ API is not responding${NC}"
    echo "Checking logs..."
    docker-compose -f docker-compose-production.yml logs --tail=50 api
    exit 1
fi

# Show logs
echo ""
echo "📋 Recent logs:"
docker-compose -f docker-compose-production.yml logs --tail=20

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Access your application at:"
echo "  Local: http://localhost:5001"
echo "  Public: http://$(curl -s ifconfig.me):5001"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose-production.yml logs -f"
echo ""
echo "To stop:"
echo "  docker-compose -f docker-compose-production.yml down"
