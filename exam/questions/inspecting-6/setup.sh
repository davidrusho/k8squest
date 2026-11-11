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
  name: crash
spec:
  containers:
  - name: crash
    image: busybox
    command: ["sh", "-c", "if [ -f /data/seen ]; then echo second-run-alive; sleep 31536000; else touch /data/seen; echo first-run-crashed; exit 1; fi"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    emptyDir: {}
EOF
for i in $(seq 1 60); do [ "$(kubectl get pod crash -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount}')" -ge 1 ] && kubectl logs crash -n "$NS" 2>/dev/null | grep -q second-run && break; sleep 3; done
