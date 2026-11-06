#!/bin/bash
# Alternative fix: the client uses the fully qualified Service name database-service.k8squest.svc.cluster.local
kubectl delete pod app-client -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<YAML || exit 1
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
        pg_isready -h database-service.k8squest.svc.cluster.local -p 5432 || echo "Connection failed"
        sleep 5
      done
YAML
