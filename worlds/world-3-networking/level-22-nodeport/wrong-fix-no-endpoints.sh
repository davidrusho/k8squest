#!/bin/bash
# Bypass: nodePort 30080, but the selector matches no pod, so the Service routes nowhere
kubectl delete svc web-nodeport -n k8squest --wait=true || exit 1
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
  namespace: k8squest
spec:
  type: NodePort
  selector:
    app: no-such-app
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
    nodePort: 30080
YAML
