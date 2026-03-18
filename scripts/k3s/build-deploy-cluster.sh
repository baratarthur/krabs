#!/bin/bash

# echo "Minikube started. Staling prometheus stack..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

source scripts/k3s/load-prometheus-images.sh

helm install monitor-service prometheus-community/kube-prometheus-stack \
  --set prometheus.prometheusSpec.image.pullPolicy=IfNotPresent \
  --set prometheusOperator.image.pullPolicy=IfNotPresent \
  --set kube-state-metrics.image.pullPolicy=IfNotPresent \
  --set grafana.enabled=false \
  --set alertmanager.enabled=false \
  --set prometheus-node-exporter.enabled=false \
  --set kubeStateMetrics.enabled=true \
  --set prometheus.prometheusSpec.replicas=1 \
  --set prometheus.service.type=NodePort \
  --set prometheus.service.nodePort=30090

echo "Prometheus stack deployed."

source scripts/k3s/load-pod-creator.sh