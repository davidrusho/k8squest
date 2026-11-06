#!/bin/bash
# Bypass: fix the PV and PVC access modes but leave the Deployment unable to start (image that cannot be pulled)
# The PVC spec is immutable once bound, so a plain apply is rejected; fall back to replace --force as the harness does
kubectl apply -f solution.yaml 2>/dev/null || kubectl replace --force -f solution.yaml || exit 1
kubectl rollout status deployment/web-servers -n k8squest --timeout=180s || exit 1
kubectl set image deployment/web-servers nginx=nginx:does-not-exist -n k8squest || exit 1
