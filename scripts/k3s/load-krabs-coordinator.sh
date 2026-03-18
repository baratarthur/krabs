#!/bin/bash

echo "Building $1 image..."
docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --sbom=false \
        -t my.private-registry.lan:5000/krabs-coordinator:latest \
        --push \
        krabs-coordinator

sudo k3s kubectl apply -f krabs-coordinator/krabs-coordinator-rbac.yaml

echo "Veryfying deploied image..."
curl -X GET http://my.private-registry.lan:5000/v2/_catalog