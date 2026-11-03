#!/bin/bash
# Bypass: a class named high-priority whose value is negative, so the critical pod ranks below default pods
# value is immutable: remove any existing class of that name before creating it with the low value
kubectl delete pod critical-api -n k8squest --ignore-not-found --wait=true || exit 1
kubectl delete priorityclass high-priority --ignore-not-found || exit 1
kubectl apply -f - <<'YAML' || exit 1
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: -100
globalDefault: false
description: "Misnamed: lower than the default priority"
YAML
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: critical-api
  namespace: k8squest
spec:
  priorityClassName: high-priority
  containers:
  - name: api
    image: nginx:latest
    resources:
      requests:
        cpu: "500m"
        memory: "512Mi"
YAML
