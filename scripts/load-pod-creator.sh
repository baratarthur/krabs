#!/bin/bash
cd pod-creator-service
docker build -t pod-creator-webservice:latest .
echo "Built pod creator image"
echo "Role binding pod creator image to minikube..."
kubectl apply -f pod-creator-rbac.yaml
echo "Loading pod creator image latest into Minikube..."
minikube image load pod-creator-webservice:latest
cd ..