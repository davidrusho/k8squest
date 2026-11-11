kubectl get po -n k8squest -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName > /opt/course/k8squest/podnode.txt
