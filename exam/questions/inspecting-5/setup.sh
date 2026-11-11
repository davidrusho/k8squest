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
  name: mc
spec:
  containers:
  - name: main
    image: busybox
    command: ["sh", "-c", "echo main-started; sleep 3600"]
  - name: sidecar
    image: busybox
    command: ["sh", "-c", "echo sidecar-ready-7731; sleep 3600"]
EOF
kubectl wait --for=condition=Ready pod/mc -n "$NS" --timeout=150s
