kubectl create sa app-sa -n k8squest --dry-run=client -o yaml > /opt/course/k8squest/sa.yaml
kubectl apply -f /opt/course/k8squest/sa.yaml
