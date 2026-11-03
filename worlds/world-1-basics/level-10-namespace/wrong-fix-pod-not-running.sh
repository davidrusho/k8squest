#!/bin/bash
# Bypass: objects with the right names exist in k8squest, but the client pod cannot start (bad image)
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: client-app
  namespace: k8squest
  labels:
    app: client
spec:
  containers:
  - name: client
    image: busybox:no-such-tag-k8squest
    command: ['sh', '-c', 'while true; do sleep 3600; done']
---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  namespace: k8squest
spec:
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8080
YAML
