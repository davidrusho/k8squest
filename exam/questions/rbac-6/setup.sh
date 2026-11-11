#!/bin/bash
# starting state for an answer-file task: a fresh answer directory first, then the cluster objects
set -e
NS="${1:-k8squest}"
rm -rf /opt/course/k8squest
mkdir -m 1777 /opt/course/k8squest
[ "$(stat -c %U /opt/course/k8squest)" = "$(id -un)" ] || { echo "answer dir not owned by $(id -un)"; exit 1; }
kubectl create sa app-sa -n "$NS"
