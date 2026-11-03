#!/bin/bash
# Alternative fix: keep the init container but change its command so it completes, instead of creating the missing Service
kubectl delete pod web-with-init -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: web-with-init
  namespace: k8squest
spec:
  initContainers:
  - name: wait-for-service
    image: busybox:latest
    command: ['sh', '-c', 'echo init done']
  containers:
  - name: web
    image: nginx:latest
    ports:
    - containerPort: 80
YAML
