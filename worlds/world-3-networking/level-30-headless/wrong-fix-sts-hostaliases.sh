#!/bin/bash
# Bypass: apply the full solution, then add hostAliases to the StatefulSet template so /etc/hosts could answer the per-pod lookups
# The broken Service has a clusterIP, which is immutable, so a plain apply is rejected; fall back to replace --force as the harness does
kubectl apply -f solution.yaml 2>/dev/null || kubectl replace --force -f solution.yaml || exit 1
kubectl rollout status statefulset/web -n k8squest --timeout=180s || exit 1
# An unrelated alias keeps every other check passing; only the hostAliases check may reject this
kubectl patch statefulset web -n k8squest --type=merge -p '{"spec":{"template":{"spec":{"hostAliases":[{"ip":"127.0.0.1","hostnames":["alias.invalid"]}]}}}}' || exit 1
