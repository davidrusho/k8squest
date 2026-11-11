kubectl apply -n k8squest -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: secpod
spec:
  containers:
  - name: secpod
    image: nginx
    volumeMounts:
    - name: creds
      mountPath: /etc/creds
  volumes:
  - name: creds
    secret:
      secretName: db-creds
EOF
