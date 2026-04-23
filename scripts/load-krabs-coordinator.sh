#!/bin/bash
echo "Building krabs coordinator image..."
docker build -t krabs-coordinator:latest coordinator
echo "Role binding krabs coordinator image to minikube..."
kubectl apply -f coordinator/krabs-coordinator-rbac.yaml
echo "Loading krabs coordinator image latest into Minikube..."
minikube image load krabs-coordinator:latest
