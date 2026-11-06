#!/bin/bash
# Alternative fix: runAsNonRoot with no runAsUser, on an image whose USER is non-root (101)
kubectl delete pod web-app -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML' || exit 1
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  namespace: k8squest
  labels:
    app: web
spec:
  containers:
  - name: nginx
    image: nginxinc/nginx-unprivileged:latest
    ports:
    - containerPort: 8080
    securityContext:
      runAsNonRoot: true
      allowPrivilegeEscalation: false
YAML
kubectl wait --for=condition=Ready pod/web-app -n k8squest --timeout=120s || exit 1
