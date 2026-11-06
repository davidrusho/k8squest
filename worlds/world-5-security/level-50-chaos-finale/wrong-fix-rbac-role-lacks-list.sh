#!/bin/bash
# Bypass: apply the full solution, then cut the Role to get only, so check 1 (RBAC) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl patch role app-role -n k8squest --type=json -p '[{"op":"replace","path":"/rules/0/verbs","value":["get"]}]' || exit 1
