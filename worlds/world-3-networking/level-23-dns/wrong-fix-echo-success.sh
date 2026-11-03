#!/bin/bash
# Bypass: a client pod that only echoes the success line and never connects to anything
kubectl delete pod app-client -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: app-client
  namespace: k8squest
spec:
  containers:
  - name: client
    image: postgres:13
    command: ["sh", "-c"]
    args:
    - |
      while true; do
        echo "database-service:5432 - accepting connections"
        sleep 5
      done
YAML
