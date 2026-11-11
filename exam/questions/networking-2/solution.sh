kubectl run tmp --image=busybox -n k8squest --rm -i --restart=Never -- nslookup web-svc > /opt/course/k8squest/nslookup.txt
