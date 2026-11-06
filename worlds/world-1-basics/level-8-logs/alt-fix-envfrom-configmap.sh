#!/bin/bash
# Alternative fix: POSTGRES_PASSWORD comes from a ConfigMap through envFrom instead of an env entry
kubectl delete pod database-app -n k8squest --ignore-not-found --wait=true || exit 1
kubectl create configmap db-env -n k8squest --from-literal=POSTGRES_PASSWORD=mysecretpassword --dry-run=client -o yaml | kubectl apply -f - || exit 1
kubectl apply -f - <<'YAML' || exit 1
apiVersion: v1
kind: Pod
metadata:
  name: database-app
  namespace: k8squest
spec:
  containers:
  - name: postgres
    image: postgres:latest
    envFrom:
    - configMapRef:
        name: db-env
    ports:
    - containerPort: 5432
YAML
kubectl wait --for=condition=Ready pod/database-app -n k8squest --timeout=120s || exit 1
