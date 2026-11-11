kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: req
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
  containers:
  - name: req
    image: nginx
EOF
