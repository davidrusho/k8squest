#!/bin/bash
# Alternative fix: a scratch image with no wget or shell (traefik/whoami) and a liveness probe on / that answers 200
kubectl apply -f - <<'YAML' || exit 1
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: k8squest
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: traefik/whoami:v1.10
        ports:
        - containerPort: 80
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 3
YAML
kubectl rollout status deployment/api-server -n k8squest --timeout=120s || exit 1
