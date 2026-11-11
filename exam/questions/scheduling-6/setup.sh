#!/bin/bash
# starting state: node and Pod objects the task builds on
set -e
NS="${1:-k8squest}"
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: ssdpod
spec:
  nodeSelector:
    disk: ssd
  containers:
  - name: ssdpod
    image: nginx:1.21
EOF
for i in $(seq 1 20); do kubectl get pod ssdpod -n "$NS" >/dev/null 2>&1 && break; sleep 1; done
kubectl create configmap ssdpod-uid -n "$NS" --from-literal=uid="$(kubectl get pod ssdpod -n "$NS" -o jsonpath='{.metadata.uid}')"
