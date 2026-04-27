#!/bin/bash

echo "Building $1 image..."
docker buildx build \
        --no-cache \
        --platform linux/amd64 \
        --provenance=false \
        --sbom=false \
        -t my.private-registry.lan:5000/krabs-coordinator:latest \
        --push \
        coordinator

sudo k3s kubectl apply -f coordinator/krabs-coordinator-rbac.yaml

echo "Veryfying deploied image..."
curl -X GET http://my.private-registry.lan:5000/v2/_catalog