#!/bin/bash
# starting state: node and Pod objects the task builds on
set -e
NS="${1:-k8squest}"
kubectl create configmap node-baseline -n "$NS" --from-literal=taints="$(kubectl get node k8squest-control-plane -o json | jq -c '[.spec.taints[]? | select(.key | startswith("node.kubernetes.io/") | not)]')"
kubectl taint node k8squest-control-plane dedicated=gpu:NoSchedule
