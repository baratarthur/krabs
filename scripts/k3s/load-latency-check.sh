#!/bin/bash

echo "Building $1 image..."
docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --sbom=false \
        -t my.private-registry.lan:5000/latency-check-webservice:latest \
        --push \
        latency-check

echo "Veryfying deploied image..."
curl -X GET http://my.private-registry.lan:5000/v2/_catalog

kubectl apply -f latency-check/latency-check-rbac.yaml
kubectl apply -f latency-check/manifest.yaml