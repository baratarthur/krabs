#!/bin/bash

# echo "Minikube started. Staling prometheus stack..."
# helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
# helm repo update

helm install monitor-service prometheus-community/kube-prometheus-stack \
  --set prometheus.prometheusSpec.image.pullPolicy=IfNotPresent \
  --set prometheusOperator.image.pullPolicy=IfNotPresent \
  --set kube-state-metrics.image.pullPolicy=IfNotPresent \
  --set grafana.enabled=false \
  --set alertmanager.enabled=false \
  --set prometheus-node-exporter.enabled=false \
  --set kubeStateMetrics.enabled=true \
  --set prometheus.prometheusSpec.replicas=1

echo "Prometheus stack deployed."

source ./scripts/build-deploy-services.sh