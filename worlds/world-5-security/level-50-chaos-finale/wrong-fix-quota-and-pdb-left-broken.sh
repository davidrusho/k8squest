#!/bin/bash
# Bypass: fix RBAC, NetworkPolicy, PriorityClass, tolerations and the security context, but leave the quota (cpu 1), the 3 x 1 CPU requests and the PDB (minAvailable 5) as broken
kubectl apply -f - <<'YAML' || exit 1
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-role
  namespace: k8squest
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-binding
  namespace: k8squest
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: app-role
subjects:
- kind: ServiceAccount
  name: app-sa
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app
  namespace: k8squest
spec:
  podSelector:
    matchLabels:
      app: chaos
  policyTypes: [Ingress, Egress]
  ingress:
  - from:
    - podSelector: {}
  egress:
  - to:
    - podSelector: {}
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - port: 53
      protocol: UDP
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: production-priority
value: 1000
globalDefault: false
description: "Production workloads"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chaos-app
  namespace: k8squest
spec:
  replicas: 3
  selector:
    matchLabels:
      app: chaos
  template:
    metadata:
      labels:
        app: chaos
    spec:
      serviceAccountName: app-sa
      priorityClassName: production-priority
      tolerations:
      - key: "dedicated"
        operator: "Exists"
        effect: "NoSchedule"
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: app
        image: nginx:latest
        command: ['sh', '-c', 'sleep 3600']
        resources:
          requests:
            cpu: "1"
            memory: "512Mi"
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          capabilities:
            drop: [ALL]
YAML
