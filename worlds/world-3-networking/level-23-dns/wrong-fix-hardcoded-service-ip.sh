#!/bin/bash
# Bypass: point the client at the Service ClusterIP instead of a DNS name, so no DNS lookup is involved
IP=$(kubectl get svc database-service -n k8squest -o jsonpath='{.spec.clusterIP}') || exit 1
[ -n "$IP" ] || exit 1
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
        pg_isready -h $IP -p 5432 || echo "Connection failed"
        sleep 5
      done
YAML
