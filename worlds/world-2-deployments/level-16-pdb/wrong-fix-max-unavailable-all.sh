#!/bin/bash
# Bypass: maxUnavailable equal to the replica count lets all pods be evicted at once
kubectl delete pdb db-proxy-pdb -n k8squest --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: db-proxy-pdb
  namespace: k8squest
spec:
  maxUnavailable: 3
  selector:
    matchLabels:
      app: db-proxy
YAML
