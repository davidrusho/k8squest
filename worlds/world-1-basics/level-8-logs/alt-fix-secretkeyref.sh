#!/bin/bash
# Alternative fix: POSTGRES_PASSWORD comes from a Secret via valueFrom.secretKeyRef instead of a literal value
kubectl delete pod database-app -n k8squest --ignore-not-found --wait=true || exit 1
kubectl create secret generic db-password -n k8squest --from-literal=password=mysecretpassword --dry-run=client -o yaml | kubectl apply -f - || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: database-app
  namespace: k8squest
spec:
  containers:
  - name: postgres
    image: postgres:latest
    env:
    - name: POSTGRES_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-password
          key: password
    ports:
    - containerPort: 5432
YAML
