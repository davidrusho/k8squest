kubectl get po -A --field-selector=status.phase!=Running > /opt/course/k8squest/notrunning.txt
