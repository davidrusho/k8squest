kubectl apply -n k8squest -f - <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: j1
spec:
  completions: 3
  parallelism: 2
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: j1
        image: busybox
        command: ["sleep", "10"]
EOF
