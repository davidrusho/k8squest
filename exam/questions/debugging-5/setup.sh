#!/bin/bash
# starting state for an answer-file task: a fresh answer directory first, then the cluster objects
set -e
NS="${1:-k8squest}"
rm -rf /opt/course/k8squest
mkdir -m 1777 /opt/course/k8squest
[ "$(stat -c %U /opt/course/k8squest)" = "$(id -un)" ] || { echo "answer dir not owned by $(id -un)"; exit 1; }
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: web
spec:
  containers:
  - name: web
    image: nginx:1.21
---
apiVersion: v1
kind: Pod
metadata:
  name: stuck
spec:
  nodeSelector:
    workload-class: gpu-heavy
  containers:
  - name: stuck
    image: nginx:1.21
---
apiVersion: v1
kind: Pod
metadata:
  name: done
spec:
  restartPolicy: Never
  containers:
  - name: done
    image: busybox
    command: ["true"]
EOF
kubectl create namespace otherns
kubectl apply -n otherns -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: blocked
spec:
  nodeSelector:
    workload-class: gpu-heavy
  containers:
  - name: blocked
    image: nginx:1.21
EOF
kubectl wait --for=condition=Ready pod/web -n "$NS" --timeout=150s
for i in $(seq 1 45); do [ "$(kubectl get pod done -n "$NS" -o jsonpath='{.status.phase}')" = "Succeeded" ] && break; sleep 2; done
