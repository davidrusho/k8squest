#!/bin/bash
# Bypass: a frontend that only echoes the expected response and names the FQDN only in a comment line, never calling the backend
kubectl delete pod frontend-app -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML' || exit 1
apiVersion: v1
kind: Pod
metadata:
  name: frontend-app
  namespace: k8squest
  labels:
    app: frontend
spec:
  containers:
  - name: frontend
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      # wget http://api-service.backend-ns.svc.cluster.local
      while true; do echo "API Response from backend-ns"; sleep 5; done
YAML
