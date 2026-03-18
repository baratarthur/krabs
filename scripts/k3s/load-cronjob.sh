#!/bin/bash
echo "Building $1 image..."
docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --sbom=false \
        -t my.private-registry.lan:5000/$1:latest \
        --push \
        cronjobs/$1

echo "Veryfying deploied image..."
curl -X GET http://my.private-registry.lan:5000/v2/_catalog