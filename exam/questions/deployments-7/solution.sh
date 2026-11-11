kubectl create deploy api --image=nginx --replicas=2 -n k8squest --dry-run=client -o yaml > /opt/course/k8squest/d.yaml
kubectl apply -n k8squest -f /opt/course/k8squest/d.yaml
