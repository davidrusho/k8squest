kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: ssdpod
spec:
  nodeSelector:
    disk: ssd
  containers:
  - name: ssdpod
    image: nginx
EOF
