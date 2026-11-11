kubectl run tmp --image=busybox -n k8squest --rm -i --restart=Never -- date > /opt/course/k8squest/date.txt
