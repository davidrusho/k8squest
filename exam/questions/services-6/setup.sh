#!/bin/bash
# starting state for an answer-file task: a fresh answer directory first, then the cluster objects
set -e
NS="${1:-k8squest}"
rm -rf /opt/course/k8squest
mkdir -m 1777 /opt/course/k8squest
[ "$(stat -c %U /opt/course/k8squest)" = "$(id -un)" ] || { echo "answer dir not owned by $(id -un)"; exit 1; }
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
EOF
kubectl rollout status deploy/web -n "$NS" --timeout=150s
for i in $(seq 1 30); do kubectl get endpointslices -n "$NS" -l kubernetes.io/service-name=web-svc -o jsonpath='{.items[*].endpoints[*].addresses[*]}' | grep -q . && break; sleep 2; done
