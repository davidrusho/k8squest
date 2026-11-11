#!/bin/bash
# starting state: node and Pod objects the task builds on
set -e
NS="${1:-k8squest}"
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: web
spec:
  containers:
  - name: web
    image: nginx:1.21
EOF
kubectl wait --for=condition=Ready pod/web -n "$NS" --timeout=150s
kubectl create configmap web-uid -n "$NS" --from-literal=uid="$(kubectl get pod web -n "$NS" -o jsonpath='{.metadata.uid}')"
