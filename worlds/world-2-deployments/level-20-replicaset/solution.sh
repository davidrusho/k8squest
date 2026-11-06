#!/bin/bash
# Scripted fix: create the Deployment, delete the standalone ReplicaSet it replaces, wait for the rollout
kubectl apply -f solution.yaml || exit 1
kubectl delete replicaset web-app-rs -n k8squest --ignore-not-found || exit 1
kubectl rollout status deployment/web-app -n k8squest --timeout=120s || exit 1
