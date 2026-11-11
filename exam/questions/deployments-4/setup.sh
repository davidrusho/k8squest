#!/bin/bash
# starting state: Deployment web with the revisions the task needs, each rolled out before the next
set -e
NS="${1:-k8squest}"
kubectl create deployment web --image=nginx:1.21 -n "$NS"
kubectl rollout status deploy/web -n "$NS" --timeout=150s
kubectl set image deploy/web nginx=nginx:1.27-alpine -n "$NS"
kubectl rollout status deploy/web -n "$NS" --timeout=150s
