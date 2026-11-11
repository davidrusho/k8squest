#!/bin/bash
# starting state: node and Pod objects the task builds on
set -e
NS="${1:-k8squest}"
kubectl taint node k8squest-control-plane dedicated=gpu:NoSchedule
