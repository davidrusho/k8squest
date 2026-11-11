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
  name: zeta
spec:
  containers:
  - name: zeta
    image: nginx:1.21
EOF
kubectl wait --for=condition=Ready pod/zeta -n "$NS" --timeout=150s
sleep 2
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: alpha
spec:
  containers:
  - name: alpha
    image: nginx:1.21
EOF
kubectl wait --for=condition=Ready pod/alpha -n "$NS" --timeout=150s
sleep 2
kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: mid
spec:
  containers:
  - name: mid
    image: nginx:1.21
EOF
kubectl wait --for=condition=Ready pod/mid -n "$NS" --timeout=150s
sleep 2
