#!/bin/bash

# echo "Minikube started. Staling prometheus stack..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

source scripts/k3s/load-prometheus-images.sh

helm install monitor-service prometheus-community/kube-prometheus-stack \
  --set prometheus.prometheusSpec.resources.requests.memory=512Mi \
  --set prometheus.prometheusSpec.resources.limits.memory=1024Mi \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.service.type=NodePort \
  --set prometheus.service.nodePorts.http=30090 \
  --set grafana.enabled=false \
  --set alertmanager.enabled=false \
  --set prometheus-node-exporter.enabled=false

echo "Prometheus stack deployed."

source scripts/k3s/load-pod-creator.sh