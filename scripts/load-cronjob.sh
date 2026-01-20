#!/bin/bash
echo "Building $1 image..."
docker build -t $1:latest cronjobs/$1
echo "Loading $1 image latest into Minikube..."
minikube image load $1:latest