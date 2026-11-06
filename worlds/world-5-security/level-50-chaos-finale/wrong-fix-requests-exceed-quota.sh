#!/bin/bash
# Bypass: apply the full solution, then lower the quota's requests.cpu below 2 x 200m, so check 8 (requests fit the quota) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl rollout status deployment/chaos-app -n k8squest --timeout=180s || exit 1
# Lowering a quota below current usage does not evict running pods, so check 9 keeps passing.
kubectl patch resourcequota chaos-quota -n k8squest --type=merge -p '{"spec":{"hard":{"requests.cpu":"300m"}}}' || exit 1
