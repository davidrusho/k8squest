kubectl get no -o jsonpath='{.items[*].metadata.name}' > /opt/course/k8squest/nodes.txt
