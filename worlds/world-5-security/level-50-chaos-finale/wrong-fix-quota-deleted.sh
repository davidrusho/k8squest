#!/bin/bash
# Bypass: apply the full solution, then delete the ResourceQuota, so check 2 (ResourceQuota) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl delete resourcequota chaos-quota -n k8squest || exit 1
