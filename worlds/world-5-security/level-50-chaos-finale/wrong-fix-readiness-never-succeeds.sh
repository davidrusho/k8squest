#!/bin/bash
# Bypass: apply the full solution, then add a readiness probe that always fails, so check 9 (pod status) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl rollout status deployment/chaos-app -n k8squest --timeout=180s || exit 1
kubectl patch deployment chaos-app -n k8squest --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"app","readinessProbe":{"exec":{"command":["false"]},"periodSeconds":5}}]}}}}' || exit 1
