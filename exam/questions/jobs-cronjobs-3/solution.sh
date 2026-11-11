kubectl create job j1 --image=busybox -n k8squest --dry-run=client -o yaml -- sleep 10 > /opt/course/k8squest/job.yaml
