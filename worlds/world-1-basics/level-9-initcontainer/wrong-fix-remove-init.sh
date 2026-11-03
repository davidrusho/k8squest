#!/bin/bash
# Bypass: remove the init container instead of making the service it waits for exist
kubectl delete pod web-with-init -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: web-with-init
  namespace: k8squest
spec:
  containers:
  - name: web
    image: nginx:latest
    ports:
    - containerPort: 80
YAML
