#!/bin/bash
# Alternative fix: leave the client on the short name `database` and create a Service with that name
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Service
metadata:
  name: database
  namespace: k8squest
spec:
  selector:
    app: db
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
YAML
