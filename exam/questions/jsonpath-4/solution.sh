kubectl get po fe -n k8squest -o jsonpath='{.spec.containers[0].image}' > /opt/course/k8squest/image.txt
