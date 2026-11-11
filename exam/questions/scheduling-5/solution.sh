kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: pinned
spec:
  nodeName: k8squest-control-plane
  containers:
  - name: pinned
    image: nginx
EOF
