#!/bin/bash

echo "Building $1 image..."
docker buildx build \
        --no-cache \
        --platform linux/amd64 \
        --provenance=false \
        --sbom=false \
        -t my.private-registry.lan:5000/pod-creator-webservice:latest \
        --push \
        pod-creator

echo "Veryfying deploied image..."
curl -X GET http://my.private-registry.lan:5000/v2/_catalog

kubectl apply -f pod-creator/pod-creator-rbac.yaml
kubectl apply -f pod-creator/manifest.yaml