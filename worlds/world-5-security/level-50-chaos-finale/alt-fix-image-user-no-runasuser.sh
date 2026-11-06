#!/bin/bash
# Alternative fix: the full solution, but with an image whose USER is non-root (101) and no runAsUser set; runAsNonRoot enforces it
kubectl apply -f solution.yaml || exit 1
kubectl patch deployment chaos-app -n k8squest --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"nginxinc/nginx-unprivileged:latest"},{"op":"remove","path":"/spec/template/spec/securityContext/runAsUser"},{"op":"remove","path":"/spec/template/spec/containers/0/securityContext/runAsUser"}]' || exit 1
kubectl rollout status deployment/chaos-app -n k8squest --timeout=120s || exit 1
