#!/bin/bash
# minikube delete
# minikube start --cpus=6 --memory=2048mb --driver=docker

echo "Prometheus installed. Building krabs images..."
# load
source scripts/load-cronjob.sh watch
source scripts/load-krabs-coordinator.sh

# deploy
kubectl apply -f krabs-coordinator/krabs-postgres.yaml
sleep 10
kubectl apply -f krabs-coordinator/krabs-coordinator-deployment.yaml
sleep 10
kubectl port-forward service/krabs-service 5002:5002
