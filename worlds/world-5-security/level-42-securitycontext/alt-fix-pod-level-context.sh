#!/bin/bash
# Alternative fix: runAsNonRoot and runAsUser set at pod level (spec.securityContext), allowPrivilegeEscalation on the container
kubectl delete pod web-app -n k8squest --ignore-not-found --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  namespace: k8squest
  labels:
    app: web
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: nginx
    image: nginxinc/nginx-unprivileged:latest
    ports:
    - containerPort: 8080
    securityContext:
      allowPrivilegeEscalation: false
YAML
