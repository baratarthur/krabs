#!/bin/bash

echo "Prometheus installed. Building krabs images..."
# load
source scripts/k3s/load-cronjob.sh watch
source scripts/k3s/load-cronjob.sh adapt
source scripts/k3s/load-krabs-coordinator.sh

# deploy
# sudo k3s kubectl apply -f coordinator/krabs-postgres.yaml
# sleep 2m
kubectl apply -f coordinator/manifest.yaml