#!/bin/bash

echo "Prometheus installed. Building krabs images..."
# load
source scripts/k3s/load-cronjob.sh watch
source scripts/k3s/load-krabs-coordinator.sh

# deploy
sudo k3s kubectl apply -f krabs-coordinator/krabs-coordinator-rbac.yaml
sudo k3s kubectl apply -f krabs-coordinator/krabs-postgres.yaml
sleep 2m
sudo k3s kubectl apply -f krabs-coordinator/krabs-coordinator-deployment.yaml