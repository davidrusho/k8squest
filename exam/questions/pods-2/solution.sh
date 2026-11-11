kubectl run web2 --image=nginx -n k8squest --dry-run=client -o yaml > /opt/course/k8squest/pod.yaml
kubectl apply -n k8squest -f /opt/course/k8squest/pod.yaml
