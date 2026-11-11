kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: tol
spec:
  tolerations:
  - key: dedicated
    operator: Equal
    value: gpu
    effect: NoSchedule
  containers:
  - name: tol
    image: nginx
EOF
