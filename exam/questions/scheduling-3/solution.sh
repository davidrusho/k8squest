kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: pref
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 1
        preference:
          matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
  containers:
  - name: pref
    image: nginx
EOF
